import React, { useState } from 'react';
import { cn } from '@/app/utils/cn';
import { ChevronDown } from 'lucide-react';
import { createAutomationAttrs } from '../../utils/automation-attrs';

interface SelectContextType {
  value: string;
  onValueChange: (value: string) => void;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const SelectContext = React.createContext<SelectContextType | undefined>(undefined);

interface SelectProps {
  value: string;
  onValueChange: (value: string) => void;
  children: React.ReactNode;
  // Automation attributes
  automationEntity?: string;
  automationAction?: string;
  automationContext?: string;
  automationState?: string;
  automationEntityId?: string | number;
  automationCustom?: Record<string, string | number | boolean>;
}

export const Select: React.FC<SelectProps> = ({ value, onValueChange, children }) => {
  const [open, setOpen] = useState(false);

  return (
    <SelectContext.Provider value={{ value, onValueChange, open, onOpenChange: setOpen }}>
      <div className="relative">
        {children}
      </div>
    </SelectContext.Provider>
  );
};

interface SelectTriggerProps {
  children: React.ReactNode;
  className?: string;
  // Automation attributes
  automationEntity?: string;
  automationAction?: string;
  automationContext?: string;
  automationState?: string;
  automationEntityId?: string | number;
  automationCustom?: Record<string, string | number | boolean>;
}

export const SelectTrigger: React.FC<SelectTriggerProps> = ({
  children,
  className,
  automationEntity,
  automationAction,
  automationContext,
  automationState,
  automationEntityId,
  automationCustom
}) => {
  const context = React.useContext(SelectContext);
  if (!context) {
    throw new Error('SelectTrigger must be used within Select');
  }

  const automationProps = automationEntity || automationAction || automationContext || automationState || automationEntityId || automationCustom ?
    createAutomationAttrs({
      entity: automationEntity,
      action: automationAction || 'toggle',
      context: automationContext,
      state: automationState || (context.open ? 'open' : 'closed'),
      entityId: automationEntityId,
      custom: {
        hasValue: !!context.value,
        isOpen: context.open,
        selectedValue: context.value,
        ...automationCustom
      }
    }) : {};

  return (
    <button
      className={cn(
        'flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50',
        className
      )}
      onClick={() => context.onOpenChange(!context.open)}
      {...automationProps}
    >
      {children}
      <ChevronDown className="h-4 w-4 opacity-50" />
    </button>
  );
};

export const SelectValue: React.FC<{ placeholder?: string }> = ({ placeholder }) => {
  const context = React.useContext(SelectContext);
  if (!context) {
    throw new Error('SelectValue must be used within Select');
  }

  return <span>{context.value || placeholder}</span>;
};

interface SelectContentProps {
  children: React.ReactNode;
  className?: string;
}

export const SelectContent: React.FC<SelectContentProps> = ({ children, className }) => {
  const context = React.useContext(SelectContext);
  if (!context) {
    throw new Error('SelectContent must be used within Select');
  }

  if (!context.open) {
    return null;
  }

  return (
    <div className={cn(
      'absolute top-full left-0 z-50 w-full mt-1 bg-white border border-gray-200 rounded-md shadow-lg max-h-60 overflow-auto',
      className
    )}>
      {children}
    </div>
  );
};

interface SelectItemProps {
  value: string;
  children: React.ReactNode;
  className?: string;
  // Automation attributes
  automationEntity?: string;
  automationAction?: string;
  automationContext?: string;
  automationState?: string;
  automationEntityId?: string | number;
  automationCustom?: Record<string, string | number | boolean>;
}

export const SelectItem: React.FC<SelectItemProps> = ({
  value,
  children,
  className,
  automationEntity,
  automationAction,
  automationContext,
  automationState,
  automationEntityId,
  automationCustom
}) => {
  const context = React.useContext(SelectContext);
  if (!context) {
    throw new Error('SelectItem must be used within Select');
  }

  const isSelected = context.value === value;
  const automationProps = automationEntity || automationAction || automationContext || automationState || automationEntityId || automationCustom ?
    createAutomationAttrs({
      entity: automationEntity,
      action: automationAction || 'selectOption',
      context: automationContext,
      state: automationState || (isSelected ? 'selected' : 'unselected'),
      entityId: automationEntityId,
      custom: {
        optionValue: value,
        optionText: typeof children === 'string' ? children : 'complex',
        isSelected,
        ...automationCustom
      }
    }) : {};

  return (
    <div
      className={cn(
        'px-3 py-2 text-sm cursor-pointer hover:bg-gray-100 focus:bg-gray-100',
        isSelected && 'bg-gray-100',
        className
      )}
      onClick={() => {
        context.onValueChange(value);
        context.onOpenChange(false);
      }}
      {...automationProps}
    >
      {children}
    </div>
  );
};