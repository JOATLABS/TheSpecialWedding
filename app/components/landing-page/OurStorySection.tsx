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
            <h2 className="text-3xl font-bold text-center mb-6 theme-primary">
              Our Story
            </h2>

            <div className="flex flex-col items-center">
              {wedding.our_story.image_url && (
                <div className={`relative w-48 h-48 mb-6 overflow-hidden ${getImageShapeClass(wedding.our_story.image_shape)}`}>
                  <Image
                    src={wedding.our_story.image_url}
                    alt="Couple"
                    fill
                    className="object-cover"
                    sizes="192px"
                  />
                </div>
              )}

              {/* Decorative open-quote */}
              <span className="text-4xl leading-none theme-accent opacity-40 mb-1 select-none">&ldquo;</span>

              <p className="text-base sm:text-lg text-gray-700 dark:text-gray-200 text-left max-w-2xl leading-relaxed italic transition-colors duration-300">
                {wedding.our_story.text}
              </p>

              {/* Decorative close-quote */}
              <span className="text-4xl leading-none theme-accent opacity-40 mt-1 self-end max-w-2xl select-none">&rdquo;</span>
            </div>
          </GlassCard>
        )}

        {/* Wedding Party */}
        {wedding.wedding_party && wedding.wedding_party.length > 0 && (
          <GlassCard className="p-6 sm:p-8" depth="near" theme={theme}>
            <h2 className="text-3xl font-bold text-center mb-8 theme-primary">
              Wedding Party
            </h2>

            <div className="space-y-8">
              {/* Bride’s Side */}
              {bridesSide.length > 0 && (
                <div>
                  <h3 className="text-xl font-semibold text-center mb-4 theme-secondary">
                    Bride's Side
                  </h3>
                  <div className="flex flex-wrap justify-center gap-4">
                    {bridesSide.map((member) => (
                      <div key={member.id} className="text-center w-24">
                        <div className="relative w-20 h-20 mx-auto mb-2 rounded-full overflow-hidden bg-gray-200 dark:bg-gray-700">
                          {member.image_url ? (
                            <Image
                              src={member.image_url}
                              alt={member.name}
                              fill
                              className="object-cover"
                              sizes="80px"
                            />
                          ) : (
                            <div className="w-full h-full flex items-center justify-center bg-wedding-rose bg-opacity-20 dark:bg-opacity-30">
                              <span className="text-xl font-bold theme-accent">
                                {member.name.charAt(0)}
                              </span>
                            </div>
                          )}
                        </div>
                        <h4 className="font-semibold text-sm text-gray-800 dark:text-gray-100">{member.name}</h4>
                        <p className="text-xs text-gray-600 dark:text-gray-300">{formatRole(member.role)}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Groom's Side */}
              {groomsSide.length > 0 && (
                <div>
                  <h3 className="text-xl font-semibold text-center mb-4 theme-secondary">
                    Groom's Side
                  </h3>
                  <div className="flex flex-wrap justify-center gap-4">
                    {groomsSide.map((member) => (
                      <div key={member.id} className="text-center w-24">
                        <div className="relative w-20 h-20 mx-auto mb-2 rounded-full overflow-hidden bg-gray-200 dark:bg-gray-700">
                            {member.image_url ? (
                            <Image
                              src={member.image_url}
                              alt={member.name}
                              fill
                              className="object-cover"
                              sizes="80px"
                            />
                            ) : (
                            <div className="w-full h-full flex items-center justify-center bg-wedding-navy bg-opacity-20">
                              <span className="text-xl font-bold theme-primary">
                              {member.name.charAt(0)}
                              </span>
                            </div>
                            )}
                        </div>
                        <h4 className="font-semibold text-sm text-gray-800 dark:text-gray-100">{member.name}</h4>
                        <p className="text-xs text-gray-600 dark:text-gray-300">{formatRole(member.role)}</p>
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
