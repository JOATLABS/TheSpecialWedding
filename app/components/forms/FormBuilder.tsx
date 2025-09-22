'use client';

import React, { useState } from 'react';
import { DragDropContext, Droppable, Draggable, DropResult } from '@hello-pangea/dnd';
import { createAutomationAttrs, formAutomationAttrs } from '@/utils/automation-attrs';

// Types
interface FormField {
 id: string;
 label: string;
 type: string;
 placeholder?: string;
 required: boolean;
 description?: string;
 options?: string[];
 order: number;
}

interface FormSettings {
 title: string;
 description?: string;
 submit_button_text: string;
 success_message: string;
 is_public: boolean;
}

interface Form {
 id: string;
 name: string;
 settings: FormSettings;
 fields: FormField[];
 is_active: boolean;
}

// Field Types Library
const FIELD_TYPES = [
 { type: 'text', label: 'Text Input', icon: 'T' },
 { type: 'email', label: 'Email', icon: '@' },
 { type: 'phone', label: 'Phone', icon: '#' },
 { type: 'number', label: 'Number', icon: '123' },
 { type: 'date', label: 'Date', icon: 'D' },
 { type: 'textarea', label: 'Text Area', icon: 'A' },
 { type: 'select', label: 'Dropdown', icon: '' },
 { type: 'radio', label: 'Radio Buttons', icon: '' },
 { type: 'checkbox', label: 'Checkboxes', icon: '' },
 { type: 'rating', label: 'Star Rating', icon: '' },
 { type: 'scale', label: 'Scale (1-10)', icon: '|--' },
] as const;

interface FormBuilderProps {
 form: Form;
 onUpdateSettings: (settings: FormSettings) => void;
 onUpdateFields: (fields: FormField[]) => void;
}

export const FormBuilder: React.FC<FormBuilderProps> = ({
 form,
 onUpdateSettings,
 onUpdateFields,
}) => {
 const [activePanel, setActivePanel] = useState<'settings' | 'fields'>('fields');
 const [selectedField, setSelectedField] = useState<string | null>(null);

 // Generate unique field ID
 const generateFieldId = () => `field_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

 // Add new field
 const addField = (fieldType: string) => {
 const newField: FormField = {
 id: generateFieldId(),
 label: `New ${fieldType} field`,
 type: fieldType,
 required: false,
 order: form.fields.length,
 ...(fieldType === 'select' || fieldType === 'radio' || fieldType === 'checkbox' 
 ? { options: ['Option 1', 'Option 2', 'Option 3'] } 
 : {}),
 ...(fieldType === 'text' || fieldType === 'email' || fieldType === 'textarea'
 ? { placeholder: `Enter ${fieldType}...` }
 : {}),
 };

 const updatedFields = [...form.fields, newField];
 onUpdateFields(updatedFields);
 setSelectedField(newField.id);
 };

 // Update field
 const updateField = (fieldId: string, updates: Partial<FormField>) => {
 const updatedFields = form.fields.map(field =>
 field.id === fieldId ? { ...field, ...updates } : field
 );
 onUpdateFields(updatedFields);
 };

 // Delete field
 const deleteField = (fieldId: string) => {
 const updatedFields = form.fields
 .filter(field => field.id !== fieldId)
 .map((field, index) => ({ ...field, order: index }));
 
 onUpdateFields(updatedFields);
 
 if (selectedField === fieldId) {
 setSelectedField(null);
 }
 };

 // Handle drag end
 const handleDragEnd = (result: DropResult) => {
 if (!result.destination) return;

 const items = Array.from(form.fields);
 const [reorderedItem] = items.splice(result.source.index, 1);
 items.splice(result.destination.index, 0, reorderedItem);

 // Update order property
 const updatedFields = items.map((field, index) => ({
 ...field,
 order: index
 }));

 onUpdateFields(updatedFields);
 };

 // Get field by ID
 const getSelectedField = () => {
 return selectedField ? form.fields.find(f => f.id === selectedField) : null;
 };

 return (
 <div className="flex h-full bg-gray-50">
 {/* Left Sidebar - Tools */}
 <div className="w-80 bg-white border-r border-gray-200 flex flex-col">
 {/* Panel Switcher */}
 <div className="border-b border-gray-200 p-4">
 <div className="flex rounded-lg bg-gray-100 p-1">
 <button
 {...createAutomationAttrs({
 entity: 'formBuilder',
 action: 'switchPanel',
 context: 'sidebar',
 state: activePanel === 'fields' ? 'active' : 'inactive',
 custom: { panel: 'fields' }
 })}
 onClick={() => setActivePanel('fields')}
 className={`flex-1 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
 activePanel === 'fields'
 ? 'bg-white text-gray-900 shadow-sm'
 : 'text-gray-600 hover:text-gray-900'
 }`}
 >
 Fields
 </button>
 <button
 {...createAutomationAttrs({
 entity: 'formBuilder',
 action: 'switchPanel',
 context: 'sidebar',
 state: activePanel === 'settings' ? 'active' : 'inactive',
 custom: { panel: 'settings' }
 })}
 onClick={() => setActivePanel('settings')}
 className={`flex-1 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
 activePanel === 'settings'
 ? 'bg-white text-gray-900 shadow-sm'
 : 'text-gray-600 hover:text-gray-900'
 }`}
 >
 Settings
 </button>
 </div>
 </div>

 {/* Panel Content */}
 <div className="flex-1 overflow-y-auto p-4">
 {activePanel === 'fields' ? (
 <FieldsPanel onAddField={addField} />
 ) : (
 <SettingsPanel 
 settings={form.settings} 
 formName={form.name}
 onUpdateSettings={onUpdateSettings}
 />
 )}
 </div>
 </div>

 {/* Center - Form Builder */}
 <div className="flex-1 flex">
 <div className="flex-1 p-6 overflow-y-auto">
 <div className="max-w-2xl mx-auto">
 <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-8">
 {/* Form Header */}
 <div className="text-center mb-8">
 <h1 className="text-3xl text-gray-900 mb-4">
 {form.settings.title}
 </h1>
 {form.settings.description && (
 <p className="text-gray-600 text-lg leading-relaxed">
 {form.settings.description}
 </p>
 )}
 </div>

 {/* Drag and Drop Fields */}
 <DragDropContext onDragEnd={handleDragEnd}>
 <Droppable droppableId="form-fields">
 {(provided) => (
 <div
 {...provided.droppableProps}
 ref={provided.innerRef}
 className="space-y-6"
 >
 {form.fields
 .sort((a, b) => a.order - b.order)
 .map((field, index) => (
 <Draggable key={field.id} draggableId={field.id} index={index}>
 {(provided, snapshot) => (
 <div
 ref={provided.innerRef}
 {...provided.draggableProps}
 className={`relative group ${
 snapshot.isDragging ? 'z-10' : ''
 } ${
 selectedField === field.id 
 ? 'ring-2 ring-indigo-500 rounded-lg' 
 : ''
 }`}
 >
 <FieldRenderer
 field={field}
 isSelected={selectedField === field.id}
 onSelect={() => setSelectedField(field.id)}
 onDelete={() => deleteField(field.id)}
 dragHandleProps={provided.dragHandleProps}
 />
 </div>
 )}
 </Draggable>
 ))}
 {provided.placeholder}
 
 {/* Empty State */}
 {form.fields.length === 0 && (
 <div className="text-center py-12 text-gray-500">
 <div className="text-4xl mb-4"></div>
 <p className="text-lg font-medium mb-2">No fields yet</p>
 <p>Add fields from the sidebar to start building your form</p>
 </div>
 )}
 </div>
 )}
 </Droppable>
 </DragDropContext>
 </div>
 </div>
 </div>

 {/* Right Sidebar - Field Properties */}
 {selectedField && (
 <div className="w-80 bg-white border-l border-gray-200">
 <FieldPropertiesPanel
 field={getSelectedField()!}
 onUpdate={(updates) => updateField(selectedField, updates)}
 onClose={() => setSelectedField(null)}
 />
 </div>
 )}
 </div>
 </div>
 );
};

// Fields Panel Component
const FieldsPanel: React.FC<{ onAddField: (type: string) => void }> = ({ onAddField }) => (
 <div>
 <h3 className="text-sm font-medium text-gray-900 mb-4">Add Fields</h3>
 <div className="grid grid-cols-1 gap-2">
 {FIELD_TYPES.map(({ type, label, icon }) => (
 <button
 {...createAutomationAttrs({
 entity: 'formBuilder',
 action: 'addField',
 context: 'fieldsPanel',
 custom: { fieldType: type, fieldLabel: label }
 })}
 key={type}
 onClick={() => onAddField(type)}
 className="flex items-center p-3 text-left border border-gray-200 rounded-lg hover:border-indigo-300 hover:bg-indigo-50 transition-colors"
 >
 <span className="text-lg mr-3">{icon}</span>
 <span className="text-sm font-medium text-gray-900">{label}</span>
 </button>
 ))}
 </div>
 </div>
);

// Settings Panel Component
const SettingsPanel: React.FC<{
 settings: FormSettings;
 formName: string;
 onUpdateSettings: (settings: FormSettings) => void;
}> = ({ settings, formName, onUpdateSettings }) => {
 const updateSetting = (key: keyof FormSettings, value: any) => {
 onUpdateSettings({ ...settings, [key]: value });
 };

 return (
 <div className="space-y-6">
 <h3 className="text-sm font-medium text-gray-900">Form Settings</h3>
 
 <div>
 <label className="block text-sm font-medium text-gray-700 mb-1">
 Form Title
 </label>
 <input
 {...createAutomationAttrs({
 entity: 'formBuilder',
 action: 'updateSetting',
 context: 'settingsPanel',
 custom: { settingType: 'title', hasValue: !!settings.title }
 })}
 type="text"
 value={settings.title}
 onChange={(e) => updateSetting('title', e.target.value)}
 className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
 />
 </div>

 <div>
 <label className="block text-sm font-medium text-gray-700 mb-1">
 Description
 </label>
 <textarea
 {...createAutomationAttrs({
 entity: 'formBuilder',
 action: 'updateSetting',
 context: 'settingsPanel',
 custom: { settingType: 'description', hasValue: !!settings.description }
 })}
 value={settings.description || ''}
 onChange={(e) => updateSetting('description', e.target.value)}
 rows={3}
 className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
 placeholder="Optional form description..."
 />
 </div>

 <div>
 <label className="block text-sm font-medium text-gray-700 mb-1">
 Submit Button Text
 </label>
 <input
 {...createAutomationAttrs({
 entity: 'formBuilder',
 action: 'updateSetting',
 context: 'settingsPanel',
 custom: { settingType: 'submit_button_text', hasValue: !!settings.submit_button_text }
 })}
 type="text"
 value={settings.submit_button_text}
 onChange={(e) => updateSetting('submit_button_text', e.target.value)}
 className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
 />
 </div>

 <div>
 <label className="block text-sm font-medium text-gray-700 mb-1">
 Success Message
 </label>
 <textarea
 {...createAutomationAttrs({
 entity: 'formBuilder',
 action: 'updateSetting',
 context: 'settingsPanel',
 custom: { settingType: 'success_message', hasValue: !!settings.success_message }
 })}
 value={settings.success_message}
 onChange={(e) => updateSetting('success_message', e.target.value)}
 rows={3}
 className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
 />
 </div>

 <div>
 <label className="flex items-center">
 <input
 {...createAutomationAttrs({
 entity: 'formBuilder',
 action: 'updateSetting',
 context: 'settingsPanel',
 state: settings.is_public ? 'checked' : 'unchecked',
 custom: { settingType: 'is_public' }
 })}
 type="checkbox"
 checked={settings.is_public}
 onChange={(e) => updateSetting('is_public', e.target.checked)}
 className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
 />
 <span className="ml-2 text-sm text-gray-700">Make form public</span>
 </label>
 </div>
 </div>
 );
};

// Field Renderer Component
const FieldRenderer: React.FC<{
 field: FormField;
 isSelected: boolean;
 onSelect: () => void;
 onDelete: () => void;
 dragHandleProps: any;
}> = ({ field, isSelected, onSelect, onDelete, dragHandleProps }) => (
 <div
 {...createAutomationAttrs({
 entity: 'formField',
 action: 'select',
 context: 'formBuilder',
 entityId: field.id,
 state: isSelected ? 'selected' : 'unselected',
 custom: { fieldType: field.type, fieldLabel: field.label }
 })}
 onClick={onSelect}
 className={`relative p-4 border-2 border-dashed cursor-pointer transition-all ${
 isSelected
 ? 'border-indigo-300 bg-indigo-50'
 : 'border-gray-200 hover:border-gray-300'
 }`}
 >
 {/* Drag Handle */}
 <div
 {...dragHandleProps}
 className="absolute top-2 left-2 cursor-move opacity-0 group-hover:opacity-100 transition-opacity"
 >
 <svg className="w-4 h-4 text-gray-400" fill="currentColor" viewBox="0 0 20 20">
 <path d="M7 2a2 2 0 00-2 2v12a2 2 0 002 2h6a2 2 0 002-2V4a2 2 0 00-2-2H7zM6 4a1 1 0 011-1h6a1 1 0 011 1v12a1 1 0 01-1 1H7a1 1 0 01-1-1V4z" />
 </svg>
 </div>

 {/* Delete Button */}
 <button
 {...createAutomationAttrs({
 entity: 'formField',
 action: 'delete',
 context: 'formBuilder',
 entityId: field.id,
 custom: { fieldType: field.type, fieldLabel: field.label }
 })}
 onClick={(e) => {
 e.stopPropagation();
 onDelete();
 }}
 className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity text-red-500 hover:text-red-700"
 >
 <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
 <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
 </svg>
 </button>

 {/* Field Content */}
 <div className="space-y-2">
 <label className="block text-sm font-medium text-gray-700">
 {field.label}
 {field.required && <span className="text-red-500 ml-1">*</span>}
 </label>
 {field.description && (
 <p className="text-sm text-gray-500">{field.description}</p>
 )}
 
 {/* Simplified field preview */}
 <div className="mt-2">
 {field.type === 'textarea' && (
 <div className="w-full h-20 border border-gray-300 rounded bg-gray-50" />
 )}
 {(field.type === 'text' || field.type === 'email' || field.type === 'phone' || field.type === 'number') && (
 <div className="w-full h-10 border border-gray-300 rounded bg-gray-50" />
 )}
 {field.type === 'select' && (
 <div className="w-full h-10 border border-gray-300 rounded bg-gray-50 flex items-center px-3">
 <span className="text-gray-400 text-sm">Select an option...</span>
 </div>
 )}
 {field.type === 'radio' && field.options && (
 <div className="space-y-2">
 {field.options.slice(0, 3).map((option, i) => (
 <div key={i} className="flex items-center">
 <div className="w-4 h-4 border border-gray-300 rounded-full mr-2" />
 <span className="text-sm text-gray-600">{option}</span>
 </div>
 ))}
 </div>
 )}
 {field.type === 'checkbox' && field.options && (
 <div className="space-y-2">
 {field.options.slice(0, 3).map((option, i) => (
 <div key={i} className="flex items-center">
 <div className="w-4 h-4 border border-gray-300 rounded mr-2" />
 <span className="text-sm text-gray-600">{option}</span>
 </div>
 ))}
 </div>
 )}
 {field.type === 'rating' && (
 <div className="flex space-x-1">
 {[1, 2, 3, 4, 5].map((i) => (
 <span key={i} className="text-gray-300 text-xl"></span>
 ))}
 </div>
 )}
 {field.type === 'scale' && (
 <div className="grid grid-cols-10 gap-1">
 {Array.from({ length: 10 }, (_, i) => (
 <div key={i} className="w-8 h-8 border border-gray-300 rounded text-xs flex items-center justify-center">
 {i + 1}
 </div>
 ))}
 </div>
 )}
 {field.type === 'date' && (
 <div className="w-full h-10 border border-gray-300 rounded bg-gray-50" />
 )}
 </div>
 </div>
 </div>
);

// Field Properties Panel Component
const FieldPropertiesPanel: React.FC<{
 field: FormField;
 onUpdate: (updates: Partial<FormField>) => void;
 onClose: () => void;
}> = ({ field, onUpdate, onClose }) => {
 const hasOptions = ['select', 'radio', 'checkbox'].includes(field.type);

 const updateOption = (index: number, value: string) => {
 const newOptions = [...(field.options || [])];
 newOptions[index] = value;
 onUpdate({ options: newOptions });
 };

 const addOption = () => {
 const newOptions = [...(field.options || []), `Option ${(field.options || []).length + 1}`];
 onUpdate({ options: newOptions });
 };

 const removeOption = (index: number) => {
 const newOptions = (field.options || []).filter((_, i) => i !== index);
 onUpdate({ options: newOptions });
 };

 return (
 <div className="h-full flex flex-col">
 {/* Header */}
 <div className="border-b border-gray-200 p-4">
 <div className="flex items-center justify-between">
 <h3 className="text-sm font-medium text-gray-900">Field Properties</h3>
 <button
 {...createAutomationAttrs({
 entity: 'formField',
 action: 'closeProperties',
 context: 'propertiesPanel',
 entityId: field.id,
 custom: { fieldType: field.type }
 })}
 onClick={onClose}
 className="text-gray-400 hover:text-gray-600"
 >
 <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
 <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
 </svg>
 </button>
 </div>
 </div>

 {/* Properties Form */}
 <div className="flex-1 overflow-y-auto p-4 space-y-6">
 <div>
 <label className="block text-sm font-medium text-gray-700 mb-1">
 Field Label
 </label>
 <input
 {...createAutomationAttrs({
 entity: 'formField',
 action: 'updateProperty',
 context: 'propertiesPanel',
 entityId: field.id,
 custom: { propertyType: 'label', fieldType: field.type, hasValue: !!field.label }
 })}
 type="text"
 value={field.label}
 onChange={(e) => onUpdate({ label: e.target.value })}
 className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
 />
 </div>

 <div>
 <label className="block text-sm font-medium text-gray-700 mb-1">
 Description
 </label>
 <textarea
 {...createAutomationAttrs({
 entity: 'formField',
 action: 'updateProperty',
 context: 'propertiesPanel',
 entityId: field.id,
 custom: { propertyType: 'description', fieldType: field.type, hasValue: !!field.description }
 })}
 value={field.description || ''}
 onChange={(e) => onUpdate({ description: e.target.value })}
 rows={2}
 className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
 placeholder="Optional field description..."
 />
 </div>

 {(field.type === 'text' || field.type === 'email' || field.type === 'textarea') && (
 <div>
 <label className="block text-sm font-medium text-gray-700 mb-1">
 Placeholder
 </label>
 <input
 {...createAutomationAttrs({
 entity: 'formField',
 action: 'updateProperty',
 context: 'propertiesPanel',
 entityId: field.id,
 custom: { propertyType: 'placeholder', fieldType: field.type, hasValue: !!field.placeholder }
 })}
 type="text"
 value={field.placeholder || ''}
 onChange={(e) => onUpdate({ placeholder: e.target.value })}
 className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
 />
 </div>
 )}

 <div>
 <label className="flex items-center">
 <input
 {...createAutomationAttrs({
 entity: 'formField',
 action: 'updateProperty',
 context: 'propertiesPanel',
 entityId: field.id,
 state: field.required ? 'checked' : 'unchecked',
 custom: { propertyType: 'required', fieldType: field.type }
 })}
 type="checkbox"
 checked={field.required}
 onChange={(e) => onUpdate({ required: e.target.checked })}
 className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
 />
 <span className="ml-2 text-sm text-gray-700">Required field</span>
 </label>
 </div>

 {hasOptions && (
 <div>
 <label className="block text-sm font-medium text-gray-700 mb-2">
 Options
 </label>
 <div className="space-y-2">
 {(field.options || []).map((option, index) => (
 <div key={index} className="flex space-x-2">
 <input
 {...createAutomationAttrs({
 entity: 'formField',
 action: 'updateOption',
 context: 'propertiesPanel',
 entityId: field.id,
 custom: {
 propertyType: 'option',
 fieldType: field.type,
 optionIndex: index,
 optionValue: option,
 hasValue: !!option
 }
 })}
 type="text"
 value={option}
 onChange={(e) => updateOption(index, e.target.value)}
 className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
 />
 <button
 {...createAutomationAttrs({
 entity: 'formField',
 action: 'removeOption',
 context: 'propertiesPanel',
 entityId: field.id,
 state: (field.options || []).length <= 1 ? 'disabled' : 'enabled',
 custom: {
 propertyType: 'option',
 fieldType: field.type,
 optionIndex: index,
 optionValue: option
 }
 })}
 onClick={() => removeOption(index)}
 className="text-red-500 hover:text-red-700 px-2"
 disabled={(field.options || []).length <= 1}
 >
 ×
 </button>
 </div>
 ))}
 <button
 {...createAutomationAttrs({
 entity: 'formField',
 action: 'addOption',
 context: 'propertiesPanel',
 entityId: field.id,
 custom: {
 propertyType: 'option',
 fieldType: field.type,
 currentOptionCount: (field.options || []).length
 }
 })}
 onClick={addOption}
 className="w-full px-3 py-2 border border-dashed border-gray-300 rounded-lg text-gray-600 hover:border-gray-400 hover:text-gray-700 transition-colors"
 >
 + Add Option
 </button>
 </div>
 </div>
 )}
 </div>
 </div>
 );
};