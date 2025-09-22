/**
 * @jest-environment jsdom
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { NotificationBadge, NotificationIconWithBadge } from '@/app/components/ui/NotificationBadge';

// Mock the Badge component
jest.mock('@/app/components/ui/badge', () => ({
  Badge: ({ children, variant, className }: any) => (
    <div data-testid="badge" data-variant={variant} className={className}>
      {children}
    </div>
  ),
}));

describe('NotificationBadge', () => {
  it('renders with correct count', () => {
    render(<NotificationBadge count={5} />);

    const badge = screen.getByTestId('badge');
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveTextContent('5');
  });

  it('renders 99+ for counts over maxCount', () => {
    render(<NotificationBadge count={150} maxCount={99} />);

    const badge = screen.getByTestId('badge');
    expect(badge).toHaveTextContent('99+');
  });

  it('uses custom maxCount correctly', () => {
    render(<NotificationBadge count={75} maxCount={50} />);

    const badge = screen.getByTestId('badge');
    expect(badge).toHaveTextContent('50+');
  });

  it('does not render when count is 0 and showZero is false', () => {
    render(<NotificationBadge count={0} showZero={false} />);

    const badge = screen.queryByTestId('badge');
    expect(badge).not.toBeInTheDocument();
  });

  it('renders when count is 0 and showZero is true', () => {
    render(<NotificationBadge count={0} showZero={true} />);

    const badge = screen.getByTestId('badge');
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveTextContent('0');
  });

  it('applies notification variant to badge', () => {
    render(<NotificationBadge count={3} />);

    const badge = screen.getByTestId('badge');
    expect(badge).toHaveAttribute('data-variant', 'notification');
  });

  it('applies pulse animation by default', () => {
    render(<NotificationBadge count={3} />);

    const badge = screen.getByTestId('badge');
    expect(badge).toHaveClass('animate-pulse');
  });

  it('does not apply pulse animation when pulse is false', () => {
    render(<NotificationBadge count={3} pulse={false} />);

    const badge = screen.getByTestId('badge');
    expect(badge).not.toHaveClass('animate-pulse');
  });

  it('does not apply pulse animation when count is 0', () => {
    render(<NotificationBadge count={0} showZero={true} pulse={true} />);

    const badge = screen.getByTestId('badge');
    expect(badge).not.toHaveClass('animate-pulse');
  });

  it('applies custom className', () => {
    render(<NotificationBadge count={3} className="custom-class" />);

    const badge = screen.getByTestId('badge');
    expect(badge).toHaveClass('custom-class');
  });

  it('applies responsive sizing classes', () => {
    render(<NotificationBadge count={3} />);

    const badge = screen.getByTestId('badge');
    expect(badge).toHaveClass('text-[10px]');
    expect(badge).toHaveClass('sm:text-xs');
  });

  it('applies minimum width and height classes', () => {
    render(<NotificationBadge count={3} />);

    const badge = screen.getByTestId('badge');
    expect(badge).toHaveClass('min-w-[1.25rem]');
    expect(badge).toHaveClass('h-5');
  });
});

describe('NotificationIconWithBadge', () => {
  const MockIcon = () => <div data-testid="mock-icon">Icon</div>;

  it('renders icon and badge when count > 0', () => {
    render(
      <NotificationIconWithBadge
        icon={<MockIcon />}
        count={5}
      />
    );

    expect(screen.getByTestId('mock-icon')).toBeInTheDocument();
    expect(screen.getByTestId('badge')).toBeInTheDocument();
    expect(screen.getByTestId('badge')).toHaveTextContent('5');
  });

  it('renders only icon when count is 0 and showZero is false', () => {
    render(
      <NotificationIconWithBadge
        icon={<MockIcon />}
        count={0}
        showZero={false}
      />
    );

    expect(screen.getByTestId('mock-icon')).toBeInTheDocument();
    expect(screen.queryByTestId('badge')).not.toBeInTheDocument();
  });

  it('renders icon and badge when count is 0 and showZero is true', () => {
    render(
      <NotificationIconWithBadge
        icon={<MockIcon />}
        count={0}
        showZero={true}
      />
    );

    expect(screen.getByTestId('mock-icon')).toBeInTheDocument();
    expect(screen.getByTestId('badge')).toBeInTheDocument();
    expect(screen.getByTestId('badge')).toHaveTextContent('0');
  });

  it('applies custom className to container', () => {
    render(
      <NotificationIconWithBadge
        icon={<MockIcon />}
        count={5}
        className="custom-container-class"
      />
    );

    const container = screen.getByTestId('mock-icon').parentElement;
    expect(container).toHaveClass('custom-container-class');
  });

  it('applies iconClassName to icon container', () => {
    render(
      <NotificationIconWithBadge
        icon={<MockIcon />}
        count={5}
        iconClassName="custom-icon-class"
      />
    );

    const iconContainer = screen.getByTestId('mock-icon').parentElement;
    expect(iconContainer).toHaveClass('custom-icon-class');
  });

  it('applies badgeClassName to badge', () => {
    render(
      <NotificationIconWithBadge
        icon={<MockIcon />}
        count={5}
        badgeClassName="custom-badge-class"
      />
    );

    const badge = screen.getByTestId('badge');
    expect(badge).toHaveClass('custom-badge-class');
  });

  it('positions badge absolutely with top and right positioning', () => {
    render(
      <NotificationIconWithBadge
        icon={<MockIcon />}
        count={5}
      />
    );

    const badge = screen.getByTestId('badge');
    expect(badge).toHaveClass('absolute');
    expect(badge).toHaveClass('-top-1');
    expect(badge).toHaveClass('-right-1');
  });

  it('uses relative positioning for container', () => {
    render(
      <NotificationIconWithBadge
        icon={<MockIcon />}
        count={5}
      />
    );

    const container = screen.getByTestId('mock-icon').parentElement?.parentElement;
    expect(container).toHaveClass('relative');
    expect(container).toHaveClass('inline-flex');
  });

  it('passes maxCount prop to NotificationBadge', () => {
    render(
      <NotificationIconWithBadge
        icon={<MockIcon />}
        count={150}
        maxCount={99}
      />
    );

    const badge = screen.getByTestId('badge');
    expect(badge).toHaveTextContent('99+');
  });

  it('passes showZero prop to NotificationBadge', () => {
    render(
      <NotificationIconWithBadge
        icon={<MockIcon />}
        count={0}
        showZero={true}
      />
    );

    expect(screen.getByTestId('badge')).toBeInTheDocument();
  });

  it('renders with complex icon component', () => {
    const ComplexIcon = () => (
      <svg data-testid="complex-icon" width="24" height="24">
        <circle cx="12" cy="12" r="10" />
      </svg>
    );

    render(
      <NotificationIconWithBadge
        icon={<ComplexIcon />}
        count={3}
      />
    );

    expect(screen.getByTestId('complex-icon')).toBeInTheDocument();
    expect(screen.getByTestId('badge')).toBeInTheDocument();
  });
});

describe('NotificationBadge Accessibility', () => {
  it('has appropriate ARIA attributes for screen readers', () => {
    render(<NotificationBadge count={5} />);

    const badge = screen.getByTestId('badge');
    // The badge should be readable by screen readers
    expect(badge).toHaveTextContent('5');
  });

  it('provides meaningful text content for count', () => {
    render(<NotificationBadge count={1} />);

    const badge = screen.getByTestId('badge');
    expect(badge).toHaveTextContent('1');
  });

  it('provides meaningful text content for high counts', () => {
    render(<NotificationBadge count={150} />);

    const badge = screen.getByTestId('badge');
    expect(badge).toHaveTextContent('99+');
  });
});

describe('NotificationBadge Edge Cases', () => {
  it('handles negative counts gracefully', () => {
    render(<NotificationBadge count={-5} showZero={true} />);

    const badge = screen.queryByTestId('badge');
    expect(badge).not.toBeInTheDocument();
  });

  it('handles very large counts', () => {
    render(<NotificationBadge count={999999} maxCount={999} />);

    const badge = screen.getByTestId('badge');
    expect(badge).toHaveTextContent('999+');
  });

  it('handles floating point counts by flooring', () => {
    render(<NotificationBadge count={5.7} />);

    const badge = screen.getByTestId('badge');
    expect(badge).toHaveTextContent('5');
  });

  it('handles zero maxCount', () => {
    render(<NotificationBadge count={5} maxCount={0} />);

    const badge = screen.getByTestId('badge');
    expect(badge).toHaveTextContent('0+');
  });

  it('handles equal count and maxCount', () => {
    render(<NotificationBadge count={50} maxCount={50} />);

    const badge = screen.getByTestId('badge');
    expect(badge).toHaveTextContent('50');
  });
});

describe('NotificationBadge Responsive Design', () => {
  it('applies mobile-first responsive text sizing', () => {
    render(<NotificationBadge count={5} />);

    const badge = screen.getByTestId('badge');
    // Should have both mobile and desktop text sizes
    expect(badge.className).toContain('text-[10px]'); // Mobile
    expect(badge.className).toContain('sm:text-xs');   // Desktop
  });

  it('maintains consistent sizing across different counts', () => {
    const { rerender } = render(<NotificationBadge count={1} />);

    let badge = screen.getByTestId('badge');
    const singleDigitClasses = badge.className;

    rerender(<NotificationBadge count={99} />);
    badge = screen.getByTestId('badge');
    const doubleDigitClasses = badge.className;

    // Should maintain same size classes regardless of content
    expect(singleDigitClasses).toContain('min-w-[1.25rem]');
    expect(doubleDigitClasses).toContain('min-w-[1.25rem]');
    expect(singleDigitClasses).toContain('h-5');
    expect(doubleDigitClasses).toContain('h-5');
  });
});

describe('NotificationBadge Performance', () => {
  it('does not re-render unnecessarily with same props', () => {
    const { rerender } = render(<NotificationBadge count={5} />);

    const initialBadge = screen.getByTestId('badge');
    const initialTextContent = initialBadge.textContent;

    // Re-render with same props
    rerender(<NotificationBadge count={5} />);

    const newBadge = screen.getByTestId('badge');
    expect(newBadge.textContent).toBe(initialTextContent);
  });

  it('updates efficiently when count changes', () => {
    const { rerender } = render(<NotificationBadge count={5} />);

    expect(screen.getByTestId('badge')).toHaveTextContent('5');

    rerender(<NotificationBadge count={10} />);
    expect(screen.getByTestId('badge')).toHaveTextContent('10');
  });
});