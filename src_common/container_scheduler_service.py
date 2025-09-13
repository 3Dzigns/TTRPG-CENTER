# container_scheduler_service.py
"""
FR-006: Container Scheduler Service
APScheduler integration for automated ingestion and log cleanup
"""

import os
import time
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR, JobExecutionEvent
import logging

from .logging import get_logger

logger = get_logger(__name__)


class ContainerSchedulerService:
    """APScheduler-based service for automated ingestion and maintenance tasks"""
    
    def __init__(self):
        self.scheduler: Optional[AsyncIOScheduler] = None
        self.is_running = False
        self.upload_directory = os.getenv("UPLOAD_DIRECTORY", "/data/uploads")
        self.log_directory = os.getenv("LOG_DIRECTORY", "/var/log/ttrpg")
        
        # Initialize scheduler
        self._setup_scheduler()
    
    def _setup_scheduler(self) -> None:
        """Setup APScheduler with appropriate configuration"""
        try:
            # Configure job stores and executors
            jobstores = {
                'default': MemoryJobStore()
            }
            
            executors = {
                'default': AsyncIOExecutor()
            }
            
            job_defaults = {
                'coalesce': True,  # Combine multiple pending executions
                'max_instances': 1,  # Prevent overlapping jobs
                'misfire_grace_time': 300  # 5 minutes grace period
            }
            
            # Create scheduler
            self.scheduler = AsyncIOScheduler(
                jobstores=jobstores,
                executors=executors,
                job_defaults=job_defaults,
                timezone='UTC'
            )
            
            # Add event listener for job monitoring
            self.scheduler.add_listener(self._job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
            
            logger.info("APScheduler initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to setup scheduler: {e}")
            self.scheduler = None
    
    def _job_listener(self, event: JobExecutionEvent) -> None:
        """Listen for job execution events"""
        if event.exception:
            logger.error(f"Scheduled job '{event.job_id}' failed: {event.exception}")
        else:
            logger.info(f"Scheduled job '{event.job_id}' completed successfully")
    
    async def start(self) -> bool:
        """
        Start the scheduler service
        
        Returns:
            True if started successfully, False otherwise
        """
        if not self.scheduler:
            logger.error("Scheduler not initialized")
            return False
        
        try:
            # Check if scheduler is enabled
            if not self._is_scheduler_enabled():
                logger.info("Scheduler disabled by configuration")
                return False
            
            # Start the scheduler
            self.scheduler.start()
            self.is_running = True
            
            # Add default jobs
            await self._add_default_jobs()
            
            logger.info("Container scheduler service started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}")
            return False
    
    async def stop(self) -> None:
        """Stop the scheduler service"""
        if self.scheduler and self.is_running:
            try:
                self.scheduler.shutdown(wait=True)
                self.is_running = False
                logger.info("Container scheduler service stopped")
            except Exception as e:
                logger.error(f"Error stopping scheduler: {e}")
    
    def _is_scheduler_enabled(self) -> bool:
        """Check if scheduler is enabled via configuration"""
        return os.getenv("SCHEDULER_ENABLED", "true").lower() in ("true", "1", "yes")
    
    async def _add_default_jobs(self) -> None:
        """Add default scheduled jobs"""
        try:
            # Ingestion job
            await self._add_ingestion_job()
            
            # Log cleanup job
            await self._add_log_cleanup_job()
            
            logger.info("Default scheduled jobs added")
            
        except Exception as e:
            logger.error(f"Failed to add default jobs: {e}")
    
    async def _add_ingestion_job(self) -> None:
        """Add automated ingestion job"""
        ingestion_cron = os.getenv("INGESTION_CRON", "0 */6 * * *")  # Every 6 hours
        
        try:
            # Parse cron expression
            trigger = CronTrigger.from_crontab(ingestion_cron, timezone='UTC')
            
            # Add job
            self.scheduler.add_job(
                func=self._run_ingestion,
                trigger=trigger,
                id='automated_ingestion',
                name='Automated File Ingestion',
                replace_existing=True
            )
            
            logger.info(f"Ingestion job scheduled with cron: {ingestion_cron}")
            
        except Exception as e:
            logger.error(f"Failed to add ingestion job: {e}")
    
    async def _add_log_cleanup_job(self) -> None:
        """Add log cleanup job"""
        cleanup_cron = os.getenv("LOG_CLEANUP_CRON", "0 2 * * *")  # Daily at 2 AM
        
        try:
            # Check if log cleanup is enabled
            if not os.getenv("LOG_CLEANUP_ENABLED", "true").lower() in ("true", "1", "yes"):
                logger.info("Log cleanup disabled by configuration")
                return
            
            # Parse cron expression
            trigger = CronTrigger.from_crontab(cleanup_cron, timezone='UTC')
            
            # Add job
            self.scheduler.add_job(
                func=self._run_log_cleanup,
                trigger=trigger,
                id='log_cleanup',
                name='Log File Cleanup',
                replace_existing=True
            )
            
            logger.info(f"Log cleanup job scheduled with cron: {cleanup_cron}")
            
        except Exception as e:
            logger.error(f"Failed to add log cleanup job: {e}")
    
    async def _run_ingestion(self) -> None:
        """Execute automated ingestion task"""
        try:
            logger.info("Starting automated ingestion...")
            
            # Check if upload directory exists and has files
            upload_path = Path(self.upload_directory)
            if not upload_path.exists():
                logger.warning(f"Upload directory does not exist: {upload_path}")
                return
            
            # Find files to process
            pdf_files = list(upload_path.glob("*.pdf"))
            if not pdf_files:
                logger.info("No PDF files found for ingestion")
                return
            
            logger.info(f"Found {len(pdf_files)} PDF files for ingestion")
            
            # Import ingestion function (avoid circular imports)
            try:
                from .pipeline_adapter import run_ingestion_pipeline
                
                # Process each file
                for pdf_file in pdf_files:
                    try:
                        logger.info(f"Processing file: {pdf_file.name}")
                        
                        # Run ingestion pipeline
                        result = await run_ingestion_pipeline(str(pdf_file))
                        
                        if result.get("success"):
                            logger.info(f"Successfully ingested: {pdf_file.name}")
                            
                            # Move processed file to archive (optional)
                            archive_path = upload_path / "processed"
                            archive_path.mkdir(exist_ok=True)
                            
                            archived_file = archive_path / f"{pdf_file.stem}_{int(time.time())}{pdf_file.suffix}"
                            pdf_file.rename(archived_file)
                            
                        else:
                            logger.error(f"Failed to ingest: {pdf_file.name}")
                            
                    except Exception as e:
                        logger.error(f"Error processing {pdf_file.name}: {e}")
                
                logger.info("Automated ingestion completed")
                
            except ImportError as e:
                logger.error(f"Could not import ingestion pipeline: {e}")
                
        except Exception as e:
            logger.error(f"Automated ingestion failed: {e}")
            raise
    
    async def _run_log_cleanup(self) -> None:
        """Execute log cleanup task"""
        try:
            logger.info("Starting log cleanup...")
            
            # Get retention period
            retention_days = int(os.getenv("LOG_RETENTION_DAYS", "5"))
            cutoff_time = datetime.now() - timedelta(days=retention_days)
            
            # Check if log directory exists
            log_path = Path(self.log_directory)
            if not log_path.exists():
                logger.warning(f"Log directory does not exist: {log_path}")
                return
            
            # Find old log files
            deleted_count = 0
            total_size = 0
            
            for log_file in log_path.glob("*.log*"):
                try:
                    # Skip current log file
                    if log_file.name.endswith('.log') and not log_file.name.endswith(f'{datetime.now().strftime("%Y-%m-%d")}.log'):
                        # Check if file is older than retention period
                        file_mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                        
                        if file_mtime < cutoff_time:
                            file_size = log_file.stat().st_size
                            log_file.unlink()
                            
                            deleted_count += 1
                            total_size += file_size
                            
                            logger.debug(f"Deleted old log file: {log_file.name}")
                
                except Exception as e:
                    logger.warning(f"Could not delete log file {log_file.name}: {e}")
            
            if deleted_count > 0:
                size_mb = total_size / (1024 * 1024)
                logger.info(f"Log cleanup completed: deleted {deleted_count} files ({size_mb:.2f} MB)")
            else:
                logger.info("No old log files found to delete")
                
        except Exception as e:
            logger.error(f"Log cleanup failed: {e}")
            raise
    
    async def add_job(
        self, 
        func: Callable, 
        trigger: str, 
        job_id: str, 
        name: Optional[str] = None,
        **trigger_args
    ) -> bool:
        """
        Add a custom scheduled job
        
        Args:
            func: Function to execute
            trigger: Trigger type ('cron', 'interval', 'date')
            job_id: Unique job identifier
            name: Optional job name
            **trigger_args: Trigger-specific arguments
            
        Returns:
            True if job added successfully, False otherwise
        """
        if not self.scheduler:
            return False
        
        try:
            # Create appropriate trigger
            if trigger == 'cron':
                job_trigger = CronTrigger(**trigger_args)
            elif trigger == 'interval':
                job_trigger = IntervalTrigger(**trigger_args)
            else:
                logger.error(f"Unsupported trigger type: {trigger}")
                return False
            
            # Add job
            self.scheduler.add_job(
                func=func,
                trigger=job_trigger,
                id=job_id,
                name=name or job_id,
                replace_existing=True
            )
            
            logger.info(f"Added custom job: {job_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add job '{job_id}': {e}")
            return False
    
    def remove_job(self, job_id: str) -> bool:
        """
        Remove a scheduled job
        
        Args:
            job_id: Job identifier to remove
            
        Returns:
            True if job removed successfully, False otherwise
        """
        if not self.scheduler:
            return False
        
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"Removed job: {job_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove job '{job_id}': {e}")
            return False
    
    def get_jobs(self) -> List[Dict[str, Any]]:
        """
        Get list of scheduled jobs
        
        Returns:
            List of job information
        """
        if not self.scheduler:
            return []
        
        try:
            jobs = []
            for job in self.scheduler.get_jobs():
                jobs.append({
                    "id": job.id,
                    "name": job.name,
                    "func": str(job.func),
                    "trigger": str(job.trigger),
                    "next_run": job.next_run_time.isoformat() if job.next_run_time else None
                })
            return jobs
            
        except Exception as e:
            logger.error(f"Failed to get jobs: {e}")
            return []
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get scheduler status
        
        Returns:
            Dictionary with scheduler status information
        """
        return {
            "enabled": self._is_scheduler_enabled(),
            "running": self.is_running,
            "scheduler_state": self.scheduler.state if self.scheduler else None,
            "job_count": len(self.scheduler.get_jobs()) if self.scheduler else 0,
            "upload_directory": self.upload_directory,
            "log_directory": self.log_directory
        }


# Global instance
_container_scheduler: Optional[ContainerSchedulerService] = None


def get_scheduler_service() -> ContainerSchedulerService:
    """Get or create the global scheduler service instance"""
    global _container_scheduler
    if _container_scheduler is None:
        _container_scheduler = ContainerSchedulerService()
    return _container_scheduler


async def start_scheduler_service() -> bool:
    """Start the global scheduler service"""
    scheduler = get_scheduler_service()
    return await scheduler.start()


async def stop_scheduler_service() -> None:
    """Stop the global scheduler service"""
    global _container_scheduler
    if _container_scheduler:
        await _container_scheduler.stop()
        _container_scheduler = None