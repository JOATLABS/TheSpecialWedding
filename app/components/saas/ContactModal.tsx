'use client';

import React, { useState } from 'react';
import { ThemeConfig } from '@/types/wedding';

interface ContactModalProps {
  isOpen: boolean;
  onClose: () => void;
  theme: ThemeConfig;
}

export const ContactModal: React.FC<ContactModalProps> = ({ isOpen, onClose, theme }) => {
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    company: '',
    phone: '',
    message: '',
    planningExperience: '',
    interestedServices: [] as string[]
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitStatus, setSubmitStatus] = useState<'idle' | 'success' | 'error'>('idle');

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleCheckboxChange = (service: string) => {
    setFormData(prev => ({
      ...prev,
      interestedServices: prev.interestedServices.includes(service)
        ? prev.interestedServices.filter(s => s !== service)
        : [...prev.interestedServices, service]
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setSubmitStatus('idle');

    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      const response = await fetch(`${baseUrl}/public/contact-form-submission`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          ...formData,
          source: 'saas_landing_page_modal',
          timestamp: new Date().toISOString()
        }),
      });

      if (response.ok) {
        setSubmitStatus('success');
        setFormData({
          name: '',
          email: '',
          company: '',
          phone: '',
          message: '',
          planningExperience: '',
          interestedServices: []
        });
      } else {
        setSubmitStatus('error');
      }
    } catch (error) {
      console.error('Contact form submission error:', error);
      setSubmitStatus('error');
    } finally {
      setIsSubmitting(false);
    }
  };

  const serviceOptions = [
    'Wedding Planning Platform',
    'AI-Powered Tools',
    'Vendor Management',
    'Guest Management & RSVP',
    'Wedding Websites',
    'Budget Tracking',
    'Timeline Management',
    'Custom Integration'
  ];

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        {/* Modal Header */}
        <div className="sticky top-0 bg-white border-b border-gray-200 p-6 rounded-t-2xl">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-2xl font-bold text-gray-900">
                Get in Touch
              </h2>
              <p className="text-gray-600 mt-1">
                Let's discuss how we can help with your wedding planning
              </p>
            </div>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 transition-colors"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Modal Content */}
        <div className="p-6">
          {submitStatus === 'success' ? (
            <div className="text-center py-8">
              <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <svg className="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <h3 className="text-2xl font-bold text-gray-900 mb-2">Thank You!</h3>
              <p className="text-gray-600 mb-6">
                We've received your inquiry and will get back to you within 24 hours.
              </p>
              <button
                onClick={onClose}
                className="text-white font-medium px-6 py-2 rounded-lg transition-colors"
                style={{ backgroundColor: theme.primary_color }}
              >
                Close
              </button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-2">
                    Full Name *
                  </label>
                  <input
                    type="text"
                    id="name"
                    name="name"
                    required
                    value={formData.name}
                    onChange={handleInputChange}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    placeholder="Your full name"
                  />
                </div>

                <div>
                  <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-2">
                    Email Address *
                  </label>
                  <input
                    type="email"
                    id="email"
                    name="email"
                    required
                    value={formData.email}
                    onChange={handleInputChange}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    placeholder="your@email.com"
                  />
                </div>

                <div>
                  <label htmlFor="company" className="block text-sm font-medium text-gray-700 mb-2">
                    Company/Business Name
                  </label>
                  <input
                    type="text"
                    id="company"
                    name="company"
                    value={formData.company}
                    onChange={handleInputChange}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    placeholder="Your wedding planning business (optional)"
                  />
                </div>

                <div>
                  <label htmlFor="phone" className="block text-sm font-medium text-gray-700 mb-2">
                    Phone Number
                  </label>
                  <input
                    type="tel"
                    id="phone"
                    name="phone"
                    value={formData.phone}
                    onChange={handleInputChange}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    placeholder="(555) 123-4567"
                  />
                </div>
              </div>

              <div>
                <label htmlFor="planningExperience" className="block text-sm font-medium text-gray-700 mb-2">
                  Wedding Planning Experience
                </label>
                <select
                  id="planningExperience"
                  name="planningExperience"
                  value={formData.planningExperience}
                  onChange={handleInputChange}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  <option value="">Select your experience level</option>
                  <option value="planning-own-wedding">Planning my own wedding</option>
                  <option value="new">Just starting as a wedding planner</option>
                  <option value="1-2-years">1-2 years experience</option>
                  <option value="3-5-years">3-5 years experience</option>
                  <option value="5-10-years">5-10 years experience</option>
                  <option value="10-plus-years">10+ years experience</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-3">
                  Which services are you most interested in? (Select all that apply)
                </label>
                <div className="grid grid-cols-2 gap-3">
                  {serviceOptions.map((service) => (
                    <label key={service} className="flex items-center space-x-3 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={formData.interestedServices.includes(service)}
                        onChange={() => handleCheckboxChange(service)}
                        className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                      />
                      <span className="text-sm text-gray-700">{service}</span>
                    </label>
                  ))}
                </div>
              </div>

              <div>
                <label htmlFor="message" className="block text-sm font-medium text-gray-700 mb-2">
                  Tell us about your needs *
                </label>
                <textarea
                  id="message"
                  name="message"
                  required
                  rows={4}
                  value={formData.message}
                  onChange={handleInputChange}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="Tell us about your wedding planning needs, current challenges, and how we can help..."
                />
              </div>

              {submitStatus === 'error' && (
                <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
                  <p className="text-red-800 text-sm">
                    There was an error submitting your form. Please try again or contact us directly.
                  </p>
                </div>
              )}

              <div className="flex justify-end space-x-3 pt-4">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-6 py-3 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-6 py-3 text-white rounded-lg transition-colors disabled:opacity-50"
                  style={{ backgroundColor: theme.primary_color }}
                >
                  {isSubmitting ? 'Sending...' : 'Send Message'}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};