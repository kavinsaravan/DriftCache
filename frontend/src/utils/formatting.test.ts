import { describe, expect, it } from 'vitest';

import { formatCurrency } from './formatting';

describe('formatCurrency', () => {
  it('formats positive dollar amounts', () => {
    expect(formatCurrency(11.72)).toBe('$11.72');
  });

  it('formats negative values and thousands separators', () => {
    expect(formatCurrency(-1234.5)).toBe('-$1,234.50');
  });
});
