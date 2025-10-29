'use client';

import React from 'react';
import { Wedding } from '@/types/wedding';
import { GlassCard } from '@/components/ui/GlassCard';

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

  const story = wedding.our_story;
  const storyParagraphs = story?.text
    ? story.text
        .split(/\n{2,}/)
        .map((paragraph) => paragraph.trim())
        .filter((paragraph) => paragraph.length > 0)
    : [];

  const midpoint = Math.ceil(storyParagraphs.length / 2);
  const columnedParagraphs = [
    storyParagraphs.slice(0, midpoint),
    storyParagraphs.slice(midpoint),
  ];

  const primaryColor = theme?.primary_color || '#1e3a5f';
  const secondaryColor = theme?.secondary_color || '#d4af37';
  const accentColor = theme?.accent_color || '#c8847e';

  return (
    <div className="max-w-6xl mx-auto px-4">
      <GlassCard className="p-8" depth="mid" theme={theme}>
        {/* Our Story */}
        {(story?.text || story?.title || story?.subtitle || (story?.key_dates?.length ?? 0) > 0) && (
          <GlassCard className="p-6 sm:p-8 md:p-10 mb-6" depth="near" theme={theme}>
            <div className="flex flex-col gap-8 xl:flex-row xl:items-start">
              {story.image_url && (
                <div className="flex justify-center xl:justify-start">
                  <div
                    className={`relative w-40 h-40 sm:w-48 sm:h-48 xl:w-56 xl:h-56 overflow-hidden shadow-lg ${getImageShapeClass(story.image_shape)}`}
                    style={{ boxShadow: `0 25px 50px -12px ${accentColor}30` }}
                  >
                    <img
                      src={story.image_url.startsWith('http')
                        ? story.image_url
                        : `https://media.thespecialwedding.com/${story.image_url}`}
                      alt="Couple"
                      className="w-full h-full object-cover"
                    />
                  </div>
                </div>
              )}

              <div className="flex-1 space-y-8">
                <div className="space-y-3 text-center xl:text-left">
                  <h2
                    className="font-wedding text-3xl sm:text-4xl font-semibold tracking-tight"
                    style={{ color: primaryColor }}
                  >
                    {story?.title?.trim() || 'Our Story'}
                  </h2>
                  {story?.subtitle && (
                    <p
                      className="text-base sm:text-lg font-light tracking-wide"
                      style={{ color: `${primaryColor}cc` }}
                    >
                      {story.subtitle}
                    </p>
                  )}
                </div>

                {storyParagraphs.length > 0 && (
                  <div
                    className="relative rounded-3xl border bg-white/80 p-6 sm:p-8 backdrop-blur"
                    style={{ borderColor: `${accentColor}40` }}
                  >
                    <span
                      className="absolute -top-8 left-8 text-6xl sm:text-7xl font-serif"
                      style={{ color: `${accentColor}80` }}
                    >
                      “
                    </span>
                    <div className="relative z-10">
                      <div className="prose prose-lg max-w-none text-gray-700 prose-headings:text-gray-900">
                        <div className="grid gap-8 lg:grid-cols-2">
                          {columnedParagraphs.map((column, columnIndex) => (
                            <div key={columnIndex} className="space-y-6">
                              {column.map((paragraph, paragraphIndex) => {
                                const isFirstParagraph = columnIndex === 0 && paragraphIndex === 0;

                                return (
                                  <p
                                    key={`${columnIndex}-${paragraphIndex}`}
                                    className={`leading-relaxed ${
                                      isFirstParagraph
                                        ? 'story-dropcap first-letter:text-5xl first-letter:font-semibold first-letter:mr-2 first-letter:float-left first-letter:leading-none'
                                        : ''
                                    }`}
                                    style={{ color: '#374151' }}
                                  >
                                    {paragraph}
                                  </p>
                                );
                              })}
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                    <div className="mt-6 flex justify-end pr-2">
                      <span className="text-4xl sm:text-5xl font-serif" style={{ color: `${accentColor}80` }}>
                        ”
                      </span>
                    </div>
                  </div>
                )}

                {story?.key_dates && story.key_dates.length > 0 && (
                  <div>
                    <h3
                      className="text-lg font-semibold uppercase tracking-[0.2em] text-center xl:text-left"
                      style={{ color: secondaryColor }}
                    >
                      Key Dates
                    </h3>
                    <div className="mt-4 grid gap-4 sm:grid-cols-2">
                      {story.key_dates.map((item, index) => (
                        <div
                          key={`${item.date}-${index}`}
                          className="rounded-2xl border bg-wedding-ivory/80 p-4 shadow-sm"
                          style={{ borderColor: `${secondaryColor}40` }}
                        >
                          <p className="text-sm font-semibold uppercase tracking-wider" style={{ color: secondaryColor }}>
                            {new Date(item.date).toLocaleDateString(undefined, {
                              year: 'numeric',
                              month: 'long',
                              day: 'numeric',
                            })}
                          </p>
                          {item.title && (
                            <p className="mt-1 text-base font-medium" style={{ color: primaryColor }}>
                              {item.title}
                            </p>
                          )}
                          {item.description && (
                            <p className="mt-2 text-sm text-gray-600">
                              {item.description}
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
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
        .heart-mask {
          -webkit-mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 512 512'%3E%3Cpath d='M462.3 62.6C407.5 15.9 326 24.3 275.7 76.2L256 96.5l-19.7-20.3C186.1 24.3 104.5 15.9 49.7 62.6c-62.8 53.6-66.1 149.8-9.9 207.9l193.5 199.8c12.5 12.9 32.8 12.9 45.3 0l193.5-199.8c56.3-58.1 53-154.3-9.8-207.9z'/%3E%3C/svg%3E") center/contain no-repeat;
          mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 512 512'%3E%3Cpath d='M462.3 62.6C407.5 15.9 326 24.3 275.7 76.2L256 96.5l-19.7-20.3C186.1 24.3 104.5 15.9 49.7 62.6c-62.8 53.6-66.1 149.8-9.9 207.9l193.5 199.8c12.5 12.9 32.8 12.9 45.3 0l193.5-199.8c56.3-58.1 53-154.3-9.8-207.9z'/%3E%3C/svg%3E") center/contain no-repeat;
        }

        .hexagon-shape {
          clip-path: polygon(30% 0%, 70% 0%, 100% 50%, 70% 100%, 30% 100%, 0% 50%);
        }

        .story-dropcap:first-letter {
          color: ${accentColor};
        }
      `}</style>
    </div>
  );
};