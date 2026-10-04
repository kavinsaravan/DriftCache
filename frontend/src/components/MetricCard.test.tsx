import { render, screen } from '@testing-library/react';
import { Activity } from 'lucide-react';
import { describe, expect, it } from 'vitest';

import MetricCard from './MetricCard';

describe('MetricCard', () => {
  it('renders the metric label, value, and subtitle', () => {
    render(
      <MetricCard
        icon={Activity}
        label="Cache hit rate"
        value="68%"
        subtitle="Last 24 hours"
      />,
    );

    expect(screen.getByText('Cache hit rate')).toBeInTheDocument();
    expect(screen.getByText('68%')).toBeInTheDocument();
    expect(screen.getByText('Last 24 hours')).toBeInTheDocument();
  });

  it('renders positive and negative trends with direction', () => {
    const { rerender } = render(
      <MetricCard icon={Activity} label="Hit rate" value="68%" trend={{ value: 4.2, isPositive: true }} />,
    );
    expect(screen.getByText('↑ 4.2%')).toHaveClass('text-green-600');

    rerender(
      <MetricCard icon={Activity} label="Hit rate" value="64%" trend={{ value: -4.2, isPositive: false }} />,
    );
    expect(screen.getByText('↓ 4.2%')).toHaveClass('text-red-600');
  });
});
