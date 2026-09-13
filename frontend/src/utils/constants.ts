/**
 * Application Constants
 */

/**
 * Query refetch intervals (in milliseconds)
 */
export const REFETCH_INTERVALS = {
  FAST: 30000,    // 30 seconds - for frequently changing metrics
  NORMAL: 60000,  // 1 minute - for standard metrics
  SLOW: 120000,   // 2 minutes - for slow-changing data
} as const;
