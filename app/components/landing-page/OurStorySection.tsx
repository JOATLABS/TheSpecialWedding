'use client';

import React from 'react';
import { Wedding } from '@/types/wedding';
import { GlassCard } from '@/components/ui/GlassCard';
import Image from 'next/image';

interface OurStorySectionProps {
  wedding: Wedding;
}

export const OurStorySection: React.FC<OurStorySectionProps> = ({ wedding }) => {
  const theme = wedding.theme_config;
  
  if (!wedding.our_story && (!wedding.wedding_party || wedding.wedding_party.length === 0)) {
    return null;
  }

  // Sort wedding party members
  const sortWeddingParty = () => {
    if (!wedding.wedding_party) return { bridesSide: [], groomsSide: [] };
    
    const bridesSide = wedding.wedding_party
      .filter(member => member.side === 'bride')
      .sort((a, b) => {
        // Maid of Honor first
        if (a.role === 'maid_of_honor' && b.role !== 'maid_of_honor') return -1;
        if (a.role !== 'maid_of_honor' && b.role === 'maid_of_honor') return 1;
        // Then alphabetically
        return a.name.localeCompare(b.name);
      });
    
    const groomsSide = wedding.wedding_party
      .filter(member => member.side === 'groom')
      .sort((a, b) => {
        // Best Man first
        if (a.role === 'best_man' && b.role !== 'best_man') return -1;
        if (a.role !== 'best_man' && b.role === 'best_man') return 1;
        // Then alphabetically
        return a.name.localeCompare(b.name);
      });
    
    return { bridesSide, groomsSide };
  };

  const { bridesSide, groomsSide } = sortWeddingParty();

  // Get image shape styles
  const getImageShapeClass = (shape?: string) => {
    switch (shape) {
      case 'heart':
        return 'heart-mask';
      case 'square':
        return 'rounded-2xl';
      case 'hexagon':
        return 'hexagon-shape';
      default:
        return 'rounded-full';
    }
  };

  // Format role display
  const formatRole = (role: string) => {
    return role.replace(/_/g, ' ')
      .split(' ')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  return (
    <div className="max-w-6xl mx-auto px-4">
      <GlassCard className="p-8" depth="mid" theme={theme}>
        {/* Our Story */}
        {wedding.our_story && wedding.our_story.text && (
          <GlassCard className="p-6 sm:p-8 mb-6" depth="near" theme={theme}>
            <h2 className="text-3xl font-bold text-center mb-6" style={{ color: theme?.primary_color || '#1e3a5f' }}>
              Our Story
            </h2>
            
            <div className="flex flex-col items-center">
              {wedding.our_story.image_url && (
                <div className={`relative w-48 h-48 mb-6 overflow-hidden ${getImageShapeClass(wedding.our_story.image_shape)}`}>
                  <img
                    src={wedding.our_story.image_url.startsWith('http') 
                      ? wedding.our_story.image_url 
                      : `https://media.thespecialwedding.com/${wedding.our_story.image_url}`}
                    alt="Couple"
                    className="w-full h-full object-cover"
                  />
                </div>
              )}
              
              <p className="text-lg text-gray-700 text-center max-w-3xl leading-relaxed">
                {wedding.our_story.text}
              </p>
            </div>
          </GlassCard>
        )}

        {/* Wedding Party */}
        {wedding.wedding_party && wedding.wedding_party.length > 0 && (
          <GlassCard className="p-6 sm:p-8" depth="near" theme={theme}>
            <h2 className="text-3xl font-bold text-center mb-8" style={{ color: theme?.primary_color || '#1e3a5f' }}>
              Wedding Party
            </h2>
            
            <div className="space-y-8">
              {/* Bride's Side */}
              {bridesSide.length > 0 && (
                <div>
                  <h3 className="text-xl font-semibold text-center mb-4" style={{ color: theme?.secondary_color || '#d4af37' }}>
                    Bride's Side
                  </h3>
                  <div className="flex flex-wrap justify-center gap-6">
                    {bridesSide.map((member) => (
                      <div key={member.id} className="text-center">
                        <div className="relative w-32 h-32 mx-auto mb-3 rounded-full overflow-hidden bg-gray-200">
                          {member.image_url ? (
                            <img
                              src={`https://media.thespecialwedding.com/${member.image_url}`}
                              alt={member.name}
                              className="w-full h-full object-cover"
                            />
                          ) : (
                            <div className="w-full h-full flex items-center justify-center bg-wedding-rose bg-opacity-20">
                              <span className="text-3xl font-bold" style={{ color: theme?.accent_color || '#c8847e' }}>
                                {member.name.charAt(0)}
                              </span>
                            </div>
                          )}
                        </div>
                        <h4 className="font-semibold text-gray-800">{member.name}</h4>
                        <p className="text-sm text-gray-600">{formatRole(member.role)}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Groom's Side */}
              {groomsSide.length > 0 && (
                <div>
                  <h3 className="text-xl font-semibold text-center mb-4" style={{ color: theme?.secondary_color || '#d4af37' }}>
                    Groom's Side
                  </h3>
                  <div className="flex flex-wrap justify-center gap-6">
                    {groomsSide.map((member) => (
                      <div key={member.id} className="text-center">
                        <div className="relative w-32 h-32 mx-auto mb-3 rounded-full overflow-hidden bg-gray-200">
                          {member.image_url ? (
                            <img
                              src={`https://media.thespecialwedding.com/${member.image_url}`}
                              alt={member.name}
                              className="w-full h-full object-cover"
                            />
                          ) : (
                            <div className="w-full h-full flex items-center justify-center bg-wedding-navy bg-opacity-20">
                              <span className="text-3xl font-bold" style={{ color: theme?.primary_color || '#1e3a5f' }}>
                                {member.name.charAt(0)}
                              </span>
                            </div>
                          )}
                        </div>
                        <h4 className="font-semibold text-gray-800">{member.name}</h4>
                        <p className="text-sm text-gray-600">{formatRole(member.role)}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </GlassCard>
        )}
      </GlassCard>

      <style jsx>{`
        .heart-shape {
          width: 192px;
          height: 192px;
          position: relative;
          transform: rotate(-45deg);
        }
        
        .heart-shape::before,
        .heart-shape::after {
          content: '';
          width: 100px;
          height: 160px;
          position: absolute;
          left: 96px;
          top: 0;
          background: red;
          border-radius: 96px 96px 0 0;
          transform: rotate(-45deg);
          transform-origin: 0 100%;
        }
        
        .heart-shape::after {
          left: 0;
          transform: rotate(45deg);
          transform-origin: 100% 100%;
        }
        
        .heart-shape img {
          position: absolute;
          width: 136px;
          height: 136px;
          top: 28px;
          left: 28px;
          transform: rotate(45deg);
          border-radius: 20px;
          object-fit: cover;
        }
        
        .hexagon-shape {
          clip-path: polygon(30% 0%, 70% 0%, 100% 50%, 70% 100%, 30% 100%, 0% 50%);
        }
      `}</style>
    </div>
  );
};