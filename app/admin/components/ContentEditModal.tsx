'use client';

import React, { useState, useEffect } from 'react';

interface ContentEditModalProps {
 isOpen: boolean;
 onClose: () => void;
 sectionType: string;
 sectionData: any;
 onSave: (updatedData: any) => Promise<void>;
 title?: string;
}

interface StatisticItem {
 value: string;
 label: string;
}

interface FeatureItem {
 title: string;
 description: string;
 icon?: string;
}

interface TestimonialItem {
 author: string;
 role: string;
 content: string;
 avatar?: string;
}

export const ContentEditModal: React.FC<ContentEditModalProps> = ({
 isOpen,
 onClose,
 sectionType,
 sectionData,
 onSave,
 title
}) => {
 const [formData, setFormData] = useState<any>({});
 const [loading, setSaving] = useState(false);
 const [errors, setErrors] = useState<Record<string, string>>({});

 useEffect(() => {
 if (isOpen && sectionData) {
 setFormData({ ...sectionData });
 setErrors({});
 }
 }, [isOpen, sectionData]);

 if (!isOpen) return null;

 const handleOverlayClick = (e: React.MouseEvent) => {
 if (e.target === e.currentTarget) {
 onClose();
 }
 };

 const validateForm = (): boolean => {
 const newErrors: Record<string, string> = {};

 switch (sectionType) {
 case 'hero':
 if (!formData.hero_title?.trim()) newErrors.hero_title = 'Title is required';
 if (!formData.hero_subtitle?.trim()) newErrors.hero_subtitle = 'Subtitle is required';
 if (!formData.hero_description?.trim()) newErrors.hero_description = 'Description is required';
 break;
 case 'statistics':
 if (!formData.statistics || formData.statistics.length === 0) {
 newErrors.statistics = 'At least one statistic is required';
 } else {
 formData.statistics.forEach((stat: StatisticItem, index: number) => {
 if (!stat.value?.trim()) newErrors[`stat_value_${index}`] = 'Value is required';
 if (!stat.label?.trim()) newErrors[`stat_label_${index}`] = 'Label is required';
 });
 }
 break;
 case 'features':
 if (!formData.features || formData.features.length === 0) {
 newErrors.features = 'At least one feature is required';
 } else {
 formData.features.forEach((feature: FeatureItem, index: number) => {
 if (!feature.title?.trim()) newErrors[`feature_title_${index}`] = 'Title is required';
 if (!feature.description?.trim()) newErrors[`feature_desc_${index}`] = 'Description is required';
 });
 }
 break;
 }

 setErrors(newErrors);
 return Object.keys(newErrors).length === 0;
 };

 const handleSave = async () => {
 if (!validateForm()) return;

 setSaving(true);
 try {
 await onSave(formData);
 onClose();
 } catch (error) {
 console.error('Failed to save:', error);
 } finally {
 setSaving(false);
 }
 };

 const renderHeroEditor = () => (
 <div className="space-y-6">
 <div>
 <label className="block text-sm font-medium text-gray-700 mb-2">
 Hero Title *
 </label>
 <input
 type="text"
 value={formData.hero_title || ''}
 onChange={(e) => setFormData({ ...formData, hero_title: e.target.value })}
 className={`w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
 errors.hero_title ? 'border-red-500' : 'border-gray-300'
 }`}
 placeholder="Enter hero title..."
 />
 {errors.hero_title && <p className="text-red-500 text-sm mt-1">{errors.hero_title}</p>}
 </div>

 <div>
 <label className="block text-sm font-medium text-gray-700 mb-2">
 Hero Subtitle *
 </label>
 <input
 type="text"
 value={formData.hero_subtitle || ''}
 onChange={(e) => setFormData({ ...formData, hero_subtitle: e.target.value })}
 className={`w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
 errors.hero_subtitle ? 'border-red-500' : 'border-gray-300'
 }`}
 placeholder="Enter hero subtitle..."
 />
 {errors.hero_subtitle && <p className="text-red-500 text-sm mt-1">{errors.hero_subtitle}</p>}
 </div>

 <div>
 <label className="block text-sm font-medium text-gray-700 mb-2">
 Hero Description *
 </label>
 <textarea
 value={formData.hero_description || ''}
 onChange={(e) => setFormData({ ...formData, hero_description: e.target.value })}
 rows={4}
 className={`w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
 errors.hero_description ? 'border-red-500' : 'border-gray-300'
 }`}
 placeholder="Enter hero description..."
 />
 {errors.hero_description && <p className="text-red-500 text-sm mt-1">{errors.hero_description}</p>}
 </div>

 <div className="grid grid-cols-2 gap-4">
 <div>
 <label className="block text-sm font-medium text-gray-700 mb-2">
 Primary CTA Button
 </label>
 <input
 type="text"
 value={formData.hero_cta_primary || ''}
 onChange={(e) => setFormData({ ...formData, hero_cta_primary: e.target.value })}
 className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
 placeholder="Get Started"
 />
 </div>
 <div>
 <label className="block text-sm font-medium text-gray-700 mb-2">
 Secondary CTA Button
 </label>
 <input
 type="text"
 value={formData.hero_cta_secondary || ''}
 onChange={(e) => setFormData({ ...formData, hero_cta_secondary: e.target.value })}
 className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
 placeholder="Learn More"
 />
 </div>
 </div>
 </div>
 );

 const renderStatisticsEditor = () => {
 const statistics = formData.statistics || [];

 const addStatistic = () => {
 setFormData({
 ...formData,
 statistics: [...statistics, { value: '', label: '' }]
 });
 };

 const removeStatistic = (index: number) => {
 const newStats = statistics.filter((_: any, i: number) => i !== index);
 setFormData({ ...formData, statistics: newStats });
 };

 const updateStatistic = (index: number, field: keyof StatisticItem, value: string) => {
 const newStats = [...statistics];
 newStats[index] = { ...newStats[index], [field]: value };
 setFormData({ ...formData, statistics: newStats });
 };

 return (
 <div className="space-y-4">
 <div className="flex justify-between items-center">
 <h4 className="font-medium text-gray-900">Statistics</h4>
 <button
 onClick={addStatistic}
 className="flex items-center text-blue-600 hover:text-blue-700 text-sm"
 >
 <span className="text-lg mr-1">+</span>
 Add Statistic
 </button>
 </div>

 {errors.statistics && <p className="text-red-500 text-sm">{errors.statistics}</p>}

 <div className="space-y-3">
 {statistics.map((stat: StatisticItem, index: number) => (
 <div key={index} className="flex items-center space-x-3 p-4 border border-gray-200 rounded-lg">
 <div className="flex-1">
 <input
 type="text"
 value={stat.value}
 onChange={(e) => updateStatistic(index, 'value', e.target.value)}
 placeholder="500+"
 className={`w-full px-3 py-2 border rounded focus:outline-none focus:ring-2 focus:ring-blue-500 ${
 errors[`stat_value_${index}`] ? 'border-red-500' : 'border-gray-300'
 }`}
 />
 {errors[`stat_value_${index}`] && (
 <p className="text-red-500 text-xs mt-1">{errors[`stat_value_${index}`]}</p>
 )}
 </div>
 <div className="flex-2">
 <input
 type="text"
 value={stat.label}
 onChange={(e) => updateStatistic(index, 'label', e.target.value)}
 placeholder="Happy Couples"
 className={`w-full px-3 py-2 border rounded focus:outline-none focus:ring-2 focus:ring-blue-500 ${
 errors[`stat_label_${index}`] ? 'border-red-500' : 'border-gray-300'
 }`}
 />
 {errors[`stat_label_${index}`] && (
 <p className="text-red-500 text-xs mt-1">{errors[`stat_label_${index}`]}</p>
 )}
 </div>
 <button
 onClick={() => removeStatistic(index)}
 className="text-red-600 hover:text-red-700"
 >
 <span className="text-lg">×</span>
 </button>
 </div>
 ))}
 </div>
 </div>
 );
 };

 const renderTrustIndicatorsEditor = () => {
 const indicators = formData.trust_indicators || [];

 const addIndicator = () => {
 setFormData({
 ...formData,
 trust_indicators: [...indicators, '']
 });
 };

 const removeIndicator = (index: number) => {
 const newIndicators = indicators.filter((_: any, i: number) => i !== index);
 setFormData({ ...formData, trust_indicators: newIndicators });
 };

 const updateIndicator = (index: number, value: string) => {
 const newIndicators = [...indicators];
 newIndicators[index] = value;
 setFormData({ ...formData, trust_indicators: newIndicators });
 };

 return (
 <div className="space-y-4">
 <div className="flex justify-between items-center">
 <h4 className="font-medium text-gray-900">Trust Indicators</h4>
 <button
 onClick={addIndicator}
 className="flex items-center text-blue-600 hover:text-blue-700 text-sm"
 >
 <span className="text-lg mr-1">+</span>
 Add Indicator
 </button>
 </div>

 <div className="space-y-3">
 {indicators.map((indicator: string, index: number) => (
 <div key={index} className="flex items-center space-x-3">
 <input
 type="text"
 value={indicator}
 onChange={(e) => updateIndicator(index, e.target.value)}
 placeholder="Free 30-day trial"
 className="flex-1 px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
 />
 <button
 onClick={() => removeIndicator(index)}
 className="text-red-600 hover:text-red-700"
 >
 <span className="text-lg">×</span>
 </button>
 </div>
 ))}
 </div>
 </div>
 );
 };

 const renderFormContent = () => {
 switch (sectionType) {
 case 'hero':
 return renderHeroEditor();
 case 'statistics':
 return renderStatisticsEditor();
 case 'trust_indicators':
 return renderTrustIndicatorsEditor();
 default:
 return (
 <div className="text-center py-8 text-gray-500">
        Content editor for “{sectionType}” is not implemented yet.
 </div>
 );
 }
 };

 return (
 <div 
 className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4"
 onClick={handleOverlayClick}
 >
 <div className="bg-white rounded-xl shadow-2xl w-full max-w-4xl max-h-[90vh] overflow-hidden">
 {/* Header */}
 <div className="flex items-center justify-between p-6 border-b border-gray-200">
 <h2 className="text-xl font-semibold text-gray-900">
 {title || `Edit ${sectionType.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())} Content`}
 </h2>
 <button
 onClick={onClose}
 className="text-gray-400 hover:text-gray-600 transition-colors"
 >
 <span className="text-2xl">×</span>
 </button>
 </div>

 {/* Content */}
 <div className="p-6 overflow-y-auto max-h-[calc(90vh-140px)]">
 {renderFormContent()}
 </div>

 {/* Footer */}
 <div className="flex items-center justify-end space-x-4 p-6 border-t border-gray-200 bg-gray-50">
 <button
 onClick={onClose}
 className="px-4 py-2 text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
 disabled={loading}
 >
 Cancel
 </button>
 <button
 onClick={handleSave}
 disabled={loading}
 className="flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
 >
 {loading ? (
 <>
 <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
 Saving...
 </>
 ) : (
 <>
 <span className="text-lg mr-2"></span>
 Save Changes
 </>
 )}
 </button>
 </div>
 </div>
 </div>
 );
};