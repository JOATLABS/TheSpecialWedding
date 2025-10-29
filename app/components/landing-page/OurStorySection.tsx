'use client';

import React from 'react';
import Image from 'next/image';
import { Wedding } from '@/types/wedding';
import { GlassCard } from '@/components/ui/GlassCard';

const getMemberInitials = (name?: string) => {
  if (!name) return '';

  const words = name
    .trim()
    .split(/\s+/)
    .filter(Boolean);

  if (words.length === 0) return '';

  return words
    .slice(0, 2)
    .map((word) => word.charAt(0).toUpperCase())
    .join('');
};

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
                <div
                  className={`relative w-48 h-48 mb-6 overflow-hidden ${getImageShapeClass(
                    wedding.our_story.image_shape
                  )}`}
                >
                  <Image
                    src={
                      wedding.our_story.image_url.startsWith('http')
                        ? wedding.our_story.image_url
                        : `https://media.thespecialwedding.com/${wedding.our_story.image_url}`
                    }
                    alt="Couple"
                    fill
                    sizes="192px"
                    className="object-cover"
                    priority
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
                        <div className="relative w-24 h-24 mx-auto mb-3 rounded-full overflow-hidden bg-gray-200 sm:w-28 sm:h-28">
                          {member.image_url ? (
                            <Image
                              src={`https://media.thespecialwedding.com/${member.image_url}`}
                              alt={member.name}
                              fill
                              sizes="(min-width: 640px) 112px, 96px"
                              className="object-cover"
                            />
                          ) : (
                            <div
                              className="w-full h-full flex items-center justify-center bg-wedding-rose bg-opacity-20"
                              role="img"
                              aria-label={`${member.name} initials`}
                            >
                              <span
                                className="text-2xl font-bold sm:text-3xl"
                                style={{ color: theme?.accent_color || '#c8847e' }}
                                aria-hidden="true"
                              >
                                {getMemberInitials(member.name)}
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
                        <div className="relative w-24 h-24 mx-auto mb-3 rounded-full overflow-hidden bg-gray-200 sm:w-28 sm:h-28">
                          {member.image_url ? (
                            <Image
                              src={`https://media.thespecialwedding.com/${member.image_url}`}
                              alt={member.name}
                              fill
                              sizes="(min-width: 640px) 112px, 96px"
                              className="object-cover"
                            />
                          ) : (
                            <div
                              className="w-full h-full flex items-center justify-center bg-wedding-navy bg-opacity-20"
                              role="img"
                              aria-label={`${member.name} initials`}
                            >
                              <span
                                className="text-2xl font-bold sm:text-3xl"
                                style={{ color: theme?.primary_color || '#1e3a5f' }}
                                aria-hidden="true"
                              >
                                {getMemberInitials(member.name)}
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
        .heart-mask {
          -webkit-mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 512 512'%3E%3Cpath d='M462.3 62.6C407.5 15.9 326 24.3 275.7 76.2L256 96.5l-19.7-20.3C186.1 24.3 104.5 15.9 49.7 62.6c-62.8 53.6-66.1 149.8-9.9 207.9l193.5 199.8c12.5 12.9 32.8 12.9 45.3 0l193.5-199.8c56.3-58.1 53-154.3-9.8-207.9z'/%3E%3C/svg%3E") center/contain no-repeat;
          mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 512 512'%3E%3Cpath d='M462.3 62.6C407.5 15.9 326 24.3 275.7 76.2L256 96.5l-19.7-20.3C186.1 24.3 104.5 15.9 49.7 62.6c-62.8 53.6-66.1 149.8-9.9 207.9l193.5 199.8c12.5 12.9 32.8 12.9 45.3 0l193.5-199.8c56.3-58.1 53-154.3-9.8-207.9z'/%3E%3C/svg%3E") center/contain no-repeat;
        }
        
        .hexagon-shape {
          clip-path: polygon(30% 0%, 70% 0%, 100% 50%, 70% 100%, 30% 100%, 0% 50%);
        }
      `}</style>
    </div>
  );
};