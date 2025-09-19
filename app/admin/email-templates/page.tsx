'use client';

import { useState, useEffect } from 'react';
import { useAdmin } from '@/contexts/AdminContext';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import {
  Plus,
  Edit,
  Trash2,
  Eye,
  Send,
  Download,
  Upload,
  Settings,
  TrendingUp,
  Mail,
  CheckCircle,
  XCircle,
  Clock,
  AlertTriangle
} from 'lucide-react';

interface EmailTemplate {
  id: string;
  name: string;
  type: 'contact_form' | 'new_user' | 'payment' | 'system_alert' | 'general';
  subject: string;
  html_content: string;
  plain_text_content?: string;
  variables: string[];
  status: 'draft' | 'active' | 'archived';
  version: number;
  is_default: boolean;
  usage_stats?: {
    sent_last_30_days: number;
    success_rate: number;
  };
  created_at: string;
  updated_at: string;
  created_by: string;
}

interface TemplateAnalytics {
  template_id: string;
  template_name: string;
  sent_count: number;
  delivered_count: number;
  opened_count: number;
  clicked_count: number;
  bounced_count: number;
  delivery_rate: number;
  open_rate: number;
  click_rate: number;
  bounce_rate: number;
}

const templateTypes = [
  { value: 'contact_form', label: 'Contact Form' },
  { value: 'new_user', label: 'New User' },
  { value: 'payment', label: 'Payment' },
  { value: 'system_alert', label: 'System Alert' },
  { value: 'general', label: 'General' }
];

const statusColors = {
  draft: 'bg-yellow-100 text-yellow-800',
  active: 'bg-green-100 text-green-800',
  archived: 'bg-gray-100 text-gray-800'
};

const typeColors = {
  contact_form: 'bg-blue-100 text-blue-800',
  new_user: 'bg-purple-100 text-purple-800',
  payment: 'bg-green-100 text-green-800',
  system_alert: 'bg-red-100 text-red-800',
  general: 'bg-gray-100 text-gray-800'
};

export default function EmailTemplatesPage() {
  const { token } = useAdmin();
  const [templates, setTemplates] = useState<EmailTemplate[]>([]);
  const [analytics, setAnalytics] = useState<TemplateAnalytics[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedTemplate, setSelectedTemplate] = useState<EmailTemplate | null>(null);
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [isPreviewDialogOpen, setIsPreviewDialogOpen] = useState(false);
  const [previewHtml, setPreviewHtml] = useState('');
  const [previewSubject, setPreviewSubject] = useState('');
  const [activeTab, setActiveTab] = useState('templates');

  // Form state
  const [formData, setFormData] = useState({
    name: '',
    type: 'contact_form',
    subject: '',
    html_content: '',
    plain_text_content: '',
    is_default: false,
    variables: [] as string[]
  });

  const [previewData, setPreviewData] = useState({
    name: 'John Doe',
    email: 'john@example.com',
    company: 'Example Corp',
    phone: '+1 (555) 123-4567',
    message: 'This is a sample message for testing the email template.',
    admin_link: 'https://www.thespecialwedding.com/'
  });

  useEffect(() => {
    fetchTemplates();
    fetchAnalytics();
  }, []);

  const fetchTemplates = async () => {
    try {
      const response = await fetch('/admin/email-templates', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        setTemplates(data.templates || []);
      } else {
        console.error('Failed to fetch templates');
      }
    } catch (error) {
      console.error('Error fetching templates:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchAnalytics = async () => {
    try {
      const response = await fetch('/admin/email-templates/analytics/overview', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        setAnalytics(data.analytics || []);
      }
    } catch (error) {
      console.error('Error fetching analytics:', error);
    }
  };

  const handleCreateTemplate = async () => {
    try {
      const response = await fetch('/admin/email-templates', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(formData)
      });

      if (response.ok) {
        setIsCreateDialogOpen(false);
        resetForm();
        fetchTemplates();
        toast.success('Template created successfully!');
      } else {
        const error = await response.json();
        toast.error(`Error creating template: ${error.detail}`);
      }
    } catch (error) {
      console.error('Error creating template:', error);
      toast.error('Error creating template');
    }
  };

  const handleUpdateTemplate = async () => {
    if (!selectedTemplate) return;

    try {
      const response = await fetch(`/admin/email-templates/${selectedTemplate.id}`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(formData)
      });

      if (response.ok) {
        setIsEditDialogOpen(false);
        resetForm();
        fetchTemplates();
        toast.success('Template updated successfully!');
      } else {
        const error = await response.json();
        alert(`Error updating template: ${error.detail}`);
      }
    } catch (error) {
      console.error('Error updating template:', error);
      toast.error('Error updating template');
    }
  };

  const handleActivateTemplate = async (templateId: string) => {
    try {
      const response = await fetch(`/admin/email-templates/${templateId}/activate`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        fetchTemplates();
        toast.success('Template activated successfully!');
      } else {
        const error = await response.json();
        alert(`Error activating template: ${error.detail}`);
      }
    } catch (error) {
      console.error('Error activating template:', error);
      toast.error('Error activating template');
    }
  };

  const handleDeleteTemplate = async (templateId: string) => {
    if (!confirm('Are you sure you want to archive this template?')) return;

    try {
      const response = await fetch(`/admin/email-templates/${templateId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        fetchTemplates();
        toast.success('Template archived successfully!');
      } else {
        const error = await response.json();
        alert(`Error archiving template: ${error.detail}`);
      }
    } catch (error) {
      console.error('Error archiving template:', error);
      toast.error('Error archiving template');
    }
  };

  const handlePreviewTemplate = async (template: EmailTemplate) => {
    try {
      const response = await fetch(`/admin/email-templates/${template.id}/preview`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          sample_data: previewData
        })
      });

      if (response.ok) {
        const data = await response.json();
        setPreviewHtml(data.rendered_html);
        setPreviewSubject(data.rendered_subject);
        setIsPreviewDialogOpen(true);
      } else {
        const error = await response.json();
        alert(`Error previewing template: ${error.detail}`);
      }
    } catch (error) {
      console.error('Error previewing template:', error);
      toast.error('Error previewing template');
    }
  };

  const handleSeedDefaults = async () => {
    if (!confirm('This will create default templates for each type. Continue?')) return;

    try {
      const response = await fetch('/admin/email-templates/seed-defaults', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        fetchTemplates();
        toast.success('Default templates created successfully!');
      } else {
        const error = await response.json();
        alert(`Error creating defaults: ${error.detail}`);
      }
    } catch (error) {
      console.error('Error creating defaults:', error);
      toast.error('Error creating defaults');
    }
  };

  const resetForm = () => {
    setFormData({
      name: '',
      type: 'contact_form',
      subject: '',
      html_content: '',
      plain_text_content: '',
      is_default: false,
      variables: []
    });
    setSelectedTemplate(null);
  };

  const openEditDialog = (template: EmailTemplate) => {
    setSelectedTemplate(template);
    setFormData({
      name: template.name,
      type: template.type,
      subject: template.subject,
      html_content: template.html_content,
      plain_text_content: template.plain_text_content || '',
      is_default: template.is_default,
      variables: template.variables
    });
    setIsEditDialogOpen(true);
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6 max-w-7xl">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-6 gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">Email Templates</h1>
          <p className="text-gray-600 mt-1">Manage email templates and delivery tracking</p>
        </div>
        <div className="flex flex-col sm:flex-row gap-2">
          <Button
            onClick={handleSeedDefaults}
            variant="outline"
            className="flex items-center gap-2"
          >
            <Settings className="h-4 w-4" />
            <span className="hidden sm:inline">Seed Defaults</span>
          </Button>
          <Button
            onClick={() => setIsCreateDialogOpen(true)}
            className="flex items-center gap-2"
          >
            <Plus className="h-4 w-4" />
            <span className="hidden sm:inline">New Template</span>
          </Button>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full grid-cols-2 lg:grid-cols-3 mb-6">
          <TabsTrigger value="templates" className="flex items-center gap-2">
            <Mail className="h-4 w-4" />
            Templates
          </TabsTrigger>
          <TabsTrigger value="analytics" className="flex items-center gap-2">
            <TrendingUp className="h-4 w-4" />
            Analytics
          </TabsTrigger>
          <TabsTrigger value="delivery" className="hidden lg:flex items-center gap-2">
            <Send className="h-4 w-4" />
            Delivery
          </TabsTrigger>
        </TabsList>

        <TabsContent value="templates" className="space-y-4">
          <div className="grid gap-4">
            {templates.map((template) => (
              <Card key={template.id} className="p-6">
                <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2 mb-2">
                      <h3 className="text-lg font-semibold text-gray-900 truncate">
                        {template.name}
                      </h3>
                      <Badge className={statusColors[template.status]}>
                        {template.status}
                      </Badge>
                      <Badge className={typeColors[template.type]}>
                        {templateTypes.find(t => t.value === template.type)?.label}
                      </Badge>
                      {template.is_default && (
                        <Badge className="bg-blue-100 text-blue-800">
                          Default
                        </Badge>
                      )}
                    </div>
                    <p className="text-sm text-gray-600 mb-2 line-clamp-2">
                      Subject: {template.subject}
                    </p>
                    <div className="flex flex-wrap items-center gap-4 text-sm text-gray-500">
                      <span>Version {template.version}</span>
                      <span>Variables: {template.variables.length}</span>
                      {template.usage_stats && (
                        <>
                          <span>{template.usage_stats.sent_last_30_days} sent (30d)</span>
                          <span>{template.usage_stats.success_rate.toFixed(1)}% success</span>
                        </>
                      )}
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handlePreviewTemplate(template)}
                    >
                      <Eye className="h-4 w-4" />
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => openEditDialog(template)}
                    >
                      <Edit className="h-4 w-4" />
                    </Button>
                    {template.status === 'draft' && (
                      <Button
                        size="sm"
                        onClick={() => handleActivateTemplate(template.id)}
                      >
                        <CheckCircle className="h-4 w-4" />
                      </Button>
                    )}
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => handleDeleteTemplate(template.id)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="analytics" className="space-y-4">
          <div className="grid gap-4">
            {analytics.map((analytic) => (
              <Card key={analytic.template_id} className="p-6">
                <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-4">
                  <div className="flex-1">
                    <h3 className="text-lg font-semibold mb-2">{analytic.template_name}</h3>
                    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 text-sm">
                      <div>
                        <span className="text-gray-600">Sent:</span>
                        <span className="font-semibold ml-1">{analytic.sent_count}</span>
                      </div>
                      <div>
                        <span className="text-gray-600">Delivered:</span>
                        <span className="font-semibold ml-1">{analytic.delivery_rate.toFixed(1)}%</span>
                      </div>
                      <div>
                        <span className="text-gray-600">Opened:</span>
                        <span className="font-semibold ml-1">{analytic.open_rate.toFixed(1)}%</span>
                      </div>
                      <div>
                        <span className="text-gray-600">Clicked:</span>
                        <span className="font-semibold ml-1">{analytic.click_rate.toFixed(1)}%</span>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    {analytic.bounce_rate > 5 && (
                      <div className="flex items-center text-red-600">
                        <AlertTriangle className="h-4 w-4 mr-1" />
                        <span className="text-sm">High Bounce</span>
                      </div>
                    )}
                    {analytic.delivery_rate > 95 && (
                      <div className="flex items-center text-green-600">
                        <CheckCircle className="h-4 w-4 mr-1" />
                        <span className="text-sm">Good Delivery</span>
                      </div>
                    )}
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="delivery" className="space-y-4">
          <div className="text-center py-8">
            <Clock className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Real-time Delivery Tracking</h3>
            <p className="text-gray-600">Live delivery status and webhook events will appear here</p>
          </div>
        </TabsContent>
      </Tabs>

      {/* Create Template Dialog */}
      <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
        <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Create New Email Template</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <Label htmlFor="name">Template Name</Label>
                <Input
                  id="name"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="Enter template name"
                />
              </div>
              <div>
                <Label htmlFor="type">Template Type</Label>
                <Select value={formData.type} onValueChange={(value) => setFormData({ ...formData, type: value as EmailTemplate['type'] })}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {templateTypes.map((type) => (
                      <SelectItem key={type.value} value={type.value}>
                        {type.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div>
              <Label htmlFor="subject">Subject Line</Label>
              <Input
                id="subject"
                value={formData.subject}
                onChange={(e) => setFormData({ ...formData, subject: e.target.value })}
                placeholder="Enter email subject (use {variables} for dynamic content)"
              />
            </div>

            <div>
              <Label htmlFor="html_content">HTML Content</Label>
              <Textarea
                id="html_content"
                value={formData.html_content}
                onChange={(e) => setFormData({ ...formData, html_content: e.target.value })}
                placeholder="Enter HTML email content (use {variables} for dynamic content)"
                className="min-h-[200px] font-mono"
              />
            </div>

            <div className="flex items-center space-x-2">
              <Switch
                id="is_default"
                checked={formData.is_default}
                onCheckedChange={(checked) => setFormData({ ...formData, is_default: checked })}
              />
              <Label htmlFor="is_default">Set as default template for this type</Label>
            </div>

            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setIsCreateDialogOpen(false)}>
                Cancel
              </Button>
              <Button onClick={handleCreateTemplate}>
                Create Template
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Edit Template Dialog */}
      <Dialog open={isEditDialogOpen} onOpenChange={setIsEditDialogOpen}>
        <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Edit Email Template</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <Label htmlFor="edit-name">Template Name</Label>
                <Input
                  id="edit-name"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="Enter template name"
                />
              </div>
              <div>
                <Label htmlFor="edit-type">Template Type</Label>
                <Select value={formData.type} onValueChange={(value) => setFormData({ ...formData, type: value as EmailTemplate['type'] })}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {templateTypes.map((type) => (
                      <SelectItem key={type.value} value={type.value}>
                        {type.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div>
              <Label htmlFor="edit-subject">Subject Line</Label>
              <Input
                id="edit-subject"
                value={formData.subject}
                onChange={(e) => setFormData({ ...formData, subject: e.target.value })}
                placeholder="Enter email subject (use {variables} for dynamic content)"
              />
            </div>

            <div>
              <Label htmlFor="edit-html_content">HTML Content</Label>
              <Textarea
                id="edit-html_content"
                value={formData.html_content}
                onChange={(e) => setFormData({ ...formData, html_content: e.target.value })}
                placeholder="Enter HTML email content (use {variables} for dynamic content)"
                className="min-h-[200px] font-mono"
              />
            </div>

            <div className="flex items-center space-x-2">
              <Switch
                id="edit-is_default"
                checked={formData.is_default}
                onCheckedChange={(checked) => setFormData({ ...formData, is_default: checked })}
              />
              <Label htmlFor="edit-is_default">Set as default template for this type</Label>
            </div>

            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setIsEditDialogOpen(false)}>
                Cancel
              </Button>
              <Button onClick={handleUpdateTemplate}>
                Update Template
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Preview Dialog */}
      <Dialog open={isPreviewDialogOpen} onOpenChange={setIsPreviewDialogOpen}>
        <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Email Preview</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>Subject Line</Label>
              <div className="p-3 bg-gray-50 rounded border">
                {previewSubject}
              </div>
            </div>
            <div>
              <Label>HTML Content</Label>
              <div className="border rounded">
                <iframe
                  srcDoc={previewHtml}
                  className="w-full h-96"
                  title="Email Preview"
                />
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}