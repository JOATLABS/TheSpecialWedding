// components/ui/card.tsx
import React from 'react';
import { createAutomationAttrs } from '../../utils/automation-attrs';

type CardProps = {
  className?: string;
  children: React.ReactNode;
  // Automation attributes
  automationEntity?: string;
  automationAction?: string;
  automationContext?: string;
  automationState?: string;
  automationEntityId?: string | number;
  automationCustom?: Record<string, string | number | boolean>;
};

// Main Card container with glassmorphism and fade-in animation
export function Card({
  className = '',
  children,
  automationEntity,
  automationAction,
  automationContext,
  automationState,
  automationEntityId,
  automationCustom
}: CardProps) {
  const automationProps = automationEntity || automationAction || automationContext || automationState || automationEntityId || automationCustom ?
    createAutomationAttrs({
      entity: automationEntity,
      action: automationAction,
      context: automationContext,
      state: automationState,
      entityId: automationEntityId,
      custom: {
        cardType: 'main',
        hasChildren: !!children,
        ...automationCustom
      }
    }) : {};

  return (
    <div
      className={
        `bg-white dark:bg-gray-800 bg-opacity-60 dark:bg-opacity-60 backdrop-blur-lg rounded-2xl shadow-lg p-6 space-y-4 animate-fade-in ${className}`
      }
      {...automationProps}
    >
      {children}
    </div>
  );
}

// Header wrapper (for title, subtitle, etc.)
export function CardHeader({
  className = '',
  children,
  automationEntity,
  automationAction,
  automationContext,
  automationState,
  automationEntityId,
  automationCustom
}: CardProps) {
  const automationProps = automationEntity || automationAction || automationContext || automationState || automationEntityId || automationCustom ?
    createAutomationAttrs({
      entity: automationEntity,
      action: automationAction,
      context: automationContext,
      state: automationState,
      entityId: automationEntityId,
      custom: {
        cardType: 'header',
        hasChildren: !!children,
        ...automationCustom
      }
    }) : {};

  return (
    <div className={`mb-4 ${className}`} {...automationProps}>{children}</div>
  );
}

// Title styling, uses your elegant font and wedding navy color
export function CardTitle({
  className = '',
  children,
  automationEntity,
  automationAction,
  automationContext,
  automationState,
  automationEntityId,
  automationCustom
}: CardProps) {
  const automationProps = automationEntity || automationAction || automationContext || automationState || automationEntityId || automationCustom ?
    createAutomationAttrs({
      entity: automationEntity,
      action: automationAction,
      context: automationContext,
      state: automationState,
      entityId: automationEntityId,
      custom: {
        cardType: 'title',
        titleText: typeof children === 'string' ? children : 'complex',
        ...automationCustom
      }
    }) : {};

  return (
    <h2
      className={`text-2xl font-elegant text-wedding-navy dark:text-gray-100 ${className}`}
      {...automationProps}
    >
      {children}
    </h2>
  );
}

// Content area inside the card
export function CardContent({
  className = '',
  children,
  automationEntity,
  automationAction,
  automationContext,
  automationState,
  automationEntityId,
  automationCustom
}: CardProps) {
  const automationProps = automationEntity || automationAction || automationContext || automationState || automationEntityId || automationCustom ?
    createAutomationAttrs({
      entity: automationEntity,
      action: automationAction,
      context: automationContext,
      state: automationState,
      entityId: automationEntityId,
      custom: {
        cardType: 'content',
        hasChildren: !!children,
        ...automationCustom
      }
    }) : {};

  return <div className={className} {...automationProps}>{children}</div>;
}
