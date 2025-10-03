# File Relocation Report

**Date:** 20251003
**Total Relocations:** 37

## Relocated Files

| Source | Destination | Reason | Method |
|--------|-------------|--------|--------|
| `pytest.log` | `env\dev\logs\historical\pytest.log` | log files | mv |
| `pytest_ing.log` | `env\dev\logs\historical\pytest_ing.log` | log files | mv |
| `manual.log` | `env\dev\logs\historical\manual.log` | log files | mv |
| `build.log` | `env\dev\logs\historical\build.log` | log files | mv |
| `build-retry.log` | `env\dev\logs\historical\build-retry.log` | log files | mv |
| `test_pass_c_extraction.py` | `tests\unit\test_pass_c_extraction.py` | test scripts | git mv |
| `test_bug_030_fix.py` | `tests\unit\test_bug_030_fix.py` | test scripts | git mv |
| `test_job_log_observability.py` | `tests\unit\test_job_log_observability.py` | test scripts | git mv |
| `container_test.pdf` | `quarantine\20251003\container_test.pdf` | test PDFs | mv |
| `container_test_final.pdf` | `quarantine\20251003\container_test_final.pdf` | test PDFs | mv |
| `final_test.pdf` | `quarantine\20251003\final_test.pdf` | test PDFs | mv |
| `final_test_complete.pdf` | `quarantine\20251003\final_test_complete.pdf` | test PDFs | mv |
| `auth.db` | `env\dev\data\auth.db` | database files | mv |
| `patch_fallback.py` | `quarantine\20251003\patch_fallback.py` | patch scripts | git mv |
| `patch_part_block.py` | `quarantine\20251003\patch_part_block.py` | patch scripts | git mv |
| `patch_part_extra.py` | `quarantine\20251003\patch_part_extra.py` | patch scripts | git mv |
| `patch_part_log_block.py` | `quarantine\20251003\patch_part_log_block.py` | patch scripts | git mv |
| `patch_plan_block.py` | `quarantine\20251003\patch_plan_block.py` | patch scripts | git mv |
| `temp_page.html` | `quarantine\20251003\temp_page.html` | temp HTML | git mv |
| `test_admin_js.html` | `quarantine\20251003\test_admin_js.html` | test HTML | git mv |
| `code-analysis-report.md` | `docs\analysis\code-analysis-report.md` | analysis reports | git mv |
| `fr-001-002-analysis-report.md` | `docs\analysis\fr-001-002-analysis-report.md` | analysis reports | git mv |
| `FR-015_VALIDATION_SUMMARY.md` | `docs\analysis\FR-015_VALIDATION_SUMMARY.md` | validation summaries | git mv |
| `IMPLEMENTATION_ROADMAP.md` | `docs\planning\IMPLEMENTATION_ROADMAP.md` | roadmaps | git mv |
| `PROJECT_INDEX.md` | `docs\PROJECT_INDEX.md` | index files | git mv |
| `FR-019-UI-Wireframe-Workflow.md` | `docs\features\FR-019-UI-Wireframe-Workflow.md` | feature docs | git mv |
| `Current_issue.md` | `docs\bugs\Current_issue.md` | issue tracking | git mv |
| `CLEANUP_SUMMARY_MVP_V2.md` | `docs\cleanup\CLEANUP_SUMMARY_MVP_V2.md` | cleanup summaries | git mv |
| `TEMP_view` | `quarantine\20251003\TEMP_view` | temp files | git mv |
| `security-report.json` | `env\dev\logs\security\security-report.json` | security reports | mv |
| `Test Uploads` | `env\dev\uploads\test-fixtures` | stray directory | mv |
| `tmp_test_job` | `quarantine\20251003\tmp_test_job` | stray directory | mv |
| `tmp_overflow` | `quarantine\20251003\tmp_overflow` | stray directory | mv |
| `manual_job` | `quarantine\20251003\manual_job` | stray directory | mv |
| `manual_job_full` | `quarantine\20251003\manual_job_full` | stray directory | mv |
| `;C` | `quarantine\20251003\unknown_C_dir` | stray directory | mv |
| `docker-data` | `quarantine\20251003\docker-data` | stray directory | mv |

## Notes

- All relocations preserve file history when using `git mv`
- Quarantined files can be restored if needed
- App files (app_*.py) require manual analysis before relocation
