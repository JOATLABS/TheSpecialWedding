import React from 'react';
import { cn } from '@/app/utils/cn';
import { createAutomationAttrs } from '../../utils/automation-attrs';

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'secondary' | 'destructive' | 'outline' | 'notification';
  // Automation attributes
  automationEntity?: string;
  automationAction?: string;
  automationContext?: string;
  automationState?: string;
  automationEntityId?: string | number;
  automationCustom?: Record<string, string | number | boolean>;
}

const Badge = React.forwardRef<HTMLDivElement, BadgeProps>(
  ({
    className,
    variant = 'default',
    automationEntity,
    automationAction,
    automationContext,
    automationState,
    automationEntityId,
    automationCustom,
    children,
    ...props
  }, ref) => {
    const automationProps = automationEntity || automationAction || automationContext || automationState || automationEntityId || automationCustom ?
      createAutomationAttrs({
        entity: automationEntity,
        action: automationAction,
        context: automationContext,
        state: automationState,
        entityId: automationEntityId,
        custom: {
          variant,
          hasChildren: !!children,
          badgeText: typeof children === 'string' ? children : 'complex',
          isNotification: variant === 'notification',
          ...automationCustom
        }
      }) : {};

    return (
      <div
        ref={ref}
        className={cn(
          'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2',
          {
            'border-transparent bg-gray-900 dark:bg-gray-100 text-gray-50 dark:text-gray-900 hover:bg-gray-900/80 dark:hover:bg-gray-100/80':
              variant === 'default',
            'border-transparent bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-100 hover:bg-gray-100/80 dark:hover:bg-gray-800/80':
              variant === 'secondary',
            'border-transparent bg-red-500 dark:bg-red-600 text-white hover:bg-red-500/80 dark:hover:bg-red-600/80':
              variant === 'destructive',
            'border-gray-200 dark:border-gray-700 text-gray-900 dark:text-gray-100 bg-transparent':
              variant === 'outline',
            'border-transparent bg-wedding-rose dark:bg-wedding-rose text-white hover:bg-wedding-rose/80 animate-pulse':
              variant === 'notification',
          },
          className
        )}
        {...automationProps}
        {...props}
      >
        {children}
      </div>
    );
  }
);
Badge.displayName = 'Badge';

export { Badge };