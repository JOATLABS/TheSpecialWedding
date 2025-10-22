// Wedding Template Types
export interface WeddingTemplate {
  id: string;
  name: string;
  description: string;
  category: 'classic' | 'modern' | 'elegant' | 'rustic' | 'minimalist';
  preview_image?: string;
  default_theme: {
    primary_color: string;
    secondary_color: string;
    accent_color: string;
    background_style: 'gradient' | 'solid' | 'image';
    font_style: 'elegant' | 'modern' | 'classic' | 'playful';
  };
  default_content: {
    rsvp_config: {
      greeting: string;
      help_text: string;
    };
    our_story: {
      text: string;
      image_shape: 'circle' | 'heart' | 'square' | 'hexagon';
    };
    faqs: Array<{
      question: string;
      answer: string;
    }>;
  };
  features: string[];
}

export const WEDDING_TEMPLATES: WeddingTemplate[] = [
  {
    id: 'special-wedding-default',
    name: 'The Special Wedding (Default)',
    description: 'The current elegant design with Modern 3D backgrounds, glass cards, and sophisticated typography',
    category: 'classic',
    default_theme: {
      primary_color: '#1e3a5f', // Navy blue - matches current
      secondary_color: '#d4af37', // Gold - matches current  
      accent_color: '#c8847e', // Rose - matches current
      background_style: 'gradient',
      font_style: 'elegant' // Playfair Display + Lora
    },
    default_content: {
      rsvp_config: {
        greeting: "Join us in celebrating our special day! Please let us know if you'll be attending.",
        help_text: "Check your phone for your personal invitation link, or contact us directly."
      },
      our_story: {
        text: "Share your love story here...",
        image_shape: 'circle'
      },
      faqs: [
        {
          question: "Hotel Recommendations",
          answer: "We'll provide hotel recommendations closer to the date."
        },
        {
          question: "What should I wear?",
          answer: "We recommend cocktail attire for the ceremony and reception."
        }
      ]
    },
    features: ['Modern 3D Backgrounds', 'Glass Card UI', 'Elegant Typography', 'Navy & Gold Theme']
  },
  {
    id: 'classic-elegance',
    name: 'Classic Elegance',
    description: 'Timeless design with sophisticated typography and traditional elements',
    category: 'classic',
    default_theme: {
      primary_color: '#1e3a5f',
      secondary_color: '#d4af37',
      accent_color: '#c8847e',
      background_style: 'gradient',
      font_style: 'elegant'
    },
    default_content: {
      rsvp_config: {
        greeting: "We cordially invite you to celebrate our special day with us.",
        help_text: "Please respond by [date] to help us plan accordingly."
      },
      our_story: {
        text: "Share your love story here...",
        image_shape: 'circle'
      },
      faqs: [
        {
          question: "What should I wear?",
          answer: "We recommend cocktail attire for the ceremony and reception."
        },
        {
          question: "Can I bring a guest?",
          answer: "Please refer to your invitation for guest policy details."
        }
      ]
    },
    features: ['Traditional Layout', 'Elegant Typography', 'Classic Color Scheme']
  },
  {
    id: 'modern-chic',
    name: 'Modern Chic',
    description: 'Contemporary design with clean lines and bold typography',
    category: 'modern',
    default_theme: {
      primary_color: '#2d3748',
      secondary_color: '#ed8936',
      accent_color: '#4fd1c7',
      background_style: 'solid',
      font_style: 'modern'
    },
    default_content: {
      rsvp_config: {
        greeting: "Join us for a celebration of love and new beginnings!",
        help_text: "Let us know if you can make it - we can't wait to see you!"
      },
      our_story: {
        text: "Tell your unique story...",
        image_shape: 'square'
      },
      faqs: [
        {
          question: "What's the vibe?",
          answer: "Think modern elegance with a fun, relaxed atmosphere."
        },
        {
          question: "Parking info?",
          answer: "Free parking is available on-site with valet service."
        }
      ]
    },
    features: ['Clean Layout', 'Bold Typography', 'Contemporary Colors']
  },
  {
    id: 'romantic-garden',
    name: 'Romantic Garden',
    description: 'Soft, romantic design inspired by nature and garden parties',
    category: 'elegant',
    default_theme: {
      primary_color: '#553c9a',
      secondary_color: '#f093fb',
      accent_color: '#f5f7fa',
      background_style: 'gradient',
      font_style: 'elegant'
    },
    default_content: {
      rsvp_config: {
        greeting: "We're blooming with excitement to celebrate with you!",
        help_text: "Please let us know if you'll be joining our garden celebration."
      },
      our_story: {
        text: "Like flowers in a garden, our love has grown...",
        image_shape: 'heart'
      },
      faqs: [
        {
          question: "Will it be outdoors?",
          answer: "Yes! We'll have a beautiful garden ceremony with indoor reception backup."
        },
        {
          question: "What about weather?",
          answer: "We have covered areas and indoor backup plans for all weather."
        }
      ]
    },
    features: ['Romantic Colors', 'Floral Elements', 'Soft Gradients']
  },
  {
    id: 'minimalist-zen',
    name: 'Minimalist Zen',
    description: 'Simple, clean design focusing on essential elements only',
    category: 'minimalist',
    default_theme: {
      primary_color: '#2d3748',
      secondary_color: '#a0aec0',
      accent_color: '#63b3ed',
      background_style: 'solid',
      font_style: 'modern'
    },
    default_content: {
      rsvp_config: {
        greeting: "Simple celebration. Pure joy. You're invited.",
        help_text: "Your presence is the only present we need."
      },
      our_story: {
        text: "Sometimes the most beautiful stories are the simplest ones...",
        image_shape: 'square'
      },
      faqs: [
        {
          question: "Gift registry?",
          answer: "Your presence is gift enough, but if you insist, see our registry page."
        },
        {
          question: "Ceremony style?",
          answer: "Simple, heartfelt, and focused on what matters most - love."
        }
      ]
    },
    features: ['Clean Lines', 'Minimal Elements', 'Focus on Content']
  }
];

export const THEME_PALETTES = [
  {
    name: 'Classic Navy & Gold',
    primary: '#1e3a5f',
    secondary: '#d4af37',
    accent: '#c8847e'
  },
  {
    name: 'Modern Charcoal & Orange',
    primary: '#2d3748',
    secondary: '#ed8936',
    accent: '#4fd1c7'
  },
  {
    name: 'Romantic Purple & Pink',
    primary: '#553c9a',
    secondary: '#f093fb',
    accent: '#f5f7fa'
  },
  {
    name: 'Sage Green & Cream',
    primary: '#68d391',
    secondary: '#f7fafc',
    accent: '#2f855a'
  },
  {
    name: 'Rose Gold & Blush',
    primary: '#ed64a6',
    secondary: '#fed7d7',
    accent: '#975a16'
  },
  {
    name: 'Deep Forest & Gold',
    primary: '#276749',
    secondary: '#ffd89b',
    accent: '#68d391'
  }
];