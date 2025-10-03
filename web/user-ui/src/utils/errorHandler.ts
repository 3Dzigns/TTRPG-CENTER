/**
 * Error Handler Utilities
 *
 * Centralized error handling and user feedback system
 */

export interface ApiError {
  message: string;
  status?: number;
  code?: string;
  details?: any;
}

export interface UserFriendlyError {
  title: string;
  message: string;
  action?: string;
  retryable: boolean;
  technical?: string;
}

/**
 * Converts API errors to user-friendly messages
 */
export const handleApiError = (error: any): UserFriendlyError => {
  // Network errors
  if (error.name === 'NetworkError' || error.message?.includes('fetch')) {
    return {
      title: 'Connection Error',
      message: 'Unable to connect to the server. Please check your internet connection.',
      action: 'Retry in a moment',
      retryable: true,
      technical: error.message
    };
  }

  // Timeout errors
  if (error.message?.includes('timeout') || error.code === 'TIMEOUT') {
    return {
      title: 'Request Timeout',
      message: 'The request took too long to complete. The server might be busy.',
      action: 'Try again with a simpler query',
      retryable: true,
      technical: error.message
    };
  }

  // Rate limiting
  if (error.status === 429) {
    return {
      title: 'Too Many Requests',
      message: 'You\'re making requests too quickly. Please wait a moment.',
      action: 'Wait 30 seconds before trying again',
      retryable: true,
      technical: 'Rate limit exceeded'
    };
  }

  // Authentication errors
  if (error.status === 401 || error.status === 403) {
    return {
      title: 'Access Denied',
      message: 'You don\'t have permission to perform this action.',
      action: 'Check your session or refresh the page',
      retryable: false,
      technical: `HTTP ${error.status}`
    };
  }

  // Server errors
  if (error.status >= 500) {
    return {
      title: 'Server Error',
      message: 'Something went wrong on our end. Our team has been notified.',
      action: 'Try again in a few minutes',
      retryable: true,
      technical: `HTTP ${error.status}: ${error.message}`
    };
  }

  // Client errors
  if (error.status >= 400 && error.status < 500) {
    return {
      title: 'Request Error',
      message: error.message || 'There was a problem with your request.',
      action: 'Check your input and try again',
      retryable: true,
      technical: `HTTP ${error.status}`
    };
  }

  // Generic errors
  return {
    title: 'Unexpected Error',
    message: 'Something unexpected happened. Please try again.',
    action: 'Contact support if this persists',
    retryable: true,
    technical: error.message || 'Unknown error'
  };
};

/**
 * Logs errors for monitoring and debugging
 */
export const logError = (error: any, context?: string) => {
  const errorData = {
    timestamp: new Date().toISOString(),
    context,
    error: {
      name: error.name,
      message: error.message,
      stack: error.stack,
      status: error.status,
      code: error.code
    },
    userAgent: navigator.userAgent,
    url: window.location.href
  };

  console.error('Application Error:', errorData);

  // In production, send to monitoring service
  if (process.env.NODE_ENV === 'production') {
    // TODO: Send to error monitoring service (e.g., Sentry)
    // sendToErrorService(errorData);
  }
};

/**
 * Retry utility with exponential backoff
 */
export const retryWithBackoff = async <T>(
  fn: () => Promise<T>,
  maxRetries: number = 3,
  baseDelay: number = 1000
): Promise<T> => {
  let lastError: any;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error;

      if (attempt === maxRetries) {
        throw error;
      }

      // Don't retry certain errors
      if (error.status === 401 || error.status === 403 || error.status === 404) {
        throw error;
      }

      // Exponential backoff: 1s, 2s, 4s, etc.
      const delay = baseDelay * Math.pow(2, attempt);
      await new Promise(resolve => setTimeout(resolve, delay));
    }
  }

  throw lastError;
};

/**
 * Connection status checker
 */
export const checkApiConnection = async (baseUrl: string): Promise<boolean> => {
  try {
    const response = await fetch(`${baseUrl}/healthz`, {
      method: 'GET',
      signal: AbortSignal.timeout(5000) // 5 second timeout
    });
    return response.ok;
  } catch (error) {
    return false;
  }
};

/**
 * Format error for display
 */
export const formatErrorForDisplay = (error: UserFriendlyError): string => {
  let message = `${error.title}: ${error.message}`;

  if (error.action) {
    message += ` ${error.action}`;
  }

  return message;
};