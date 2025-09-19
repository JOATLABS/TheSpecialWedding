import React from 'react';
import { cn } from '@/app/utils/cn';
import { createAutomationAttrs } from '../../utils/automation-attrs';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  // Automation attributes
  automationEntity?: string;
  automationAction?: string;
  automationContext?: string;
  automationState?: string;
  automationEntityId?: string | number;
  automationCustom?: Record<string, string | number | boolean>;
}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({
    className,
    type = 'text',
    automationEntity,
    automationAction,
    automationContext,
    automationState,
    automationEntityId,
    automationCustom,
    disabled,
    value,
    placeholder,
    required,
    ...props
  }, ref) => {
    const automationProps = automationEntity || automationAction || automationContext || automationState || automationEntityId || automationCustom ?
      createAutomationAttrs({
        entity: automationEntity,
        action: automationAction,
        context: automationContext,
        state: automationState || (disabled ? 'disabled' : 'enabled'),
        entityId: automationEntityId,
        custom: {
          inputType: type,
          hasValue: !!value,
          hasPlaceholder: !!placeholder,
          isRequired: !!required,
          ...automationCustom
        }
      }) : {};

    return (
      <input
        type={type}
        className={cn(
          'flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50',
          className
        )}
        ref={ref}
        disabled={disabled}
        value={value}
        placeholder={placeholder}
        required={required}
        {...automationProps}
        {...props}
      />
    );
  }
);
Input.displayName = 'Input';

export { Input };