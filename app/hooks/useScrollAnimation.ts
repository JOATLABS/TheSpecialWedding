
import { useEffect, useState, useRef } from 'react';
import { SaasFullConfig } from '../admin/saas/page';

type AnimationSettings = Pick<SaasFullConfig,
  'animations_enabled' |
  'scroll_animations' |
  'animation_speed'
>;

export const useScrollAnimation = (settings: AnimationSettings) => {
  const [isVisible, setIsVisible] = useState(false);
  const ref = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!settings.animations_enabled || !settings.scroll_animations) {
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
          if (ref.current) {
            observer.unobserve(ref.current);
          }
        }
      },
      {
        rootMargin: '0px',
        threshold: 0.1,
      }
    );

    if (ref.current) {
      observer.observe(ref.current);
    }

    return () => {
      if (ref.current) {
        observer.unobserve(ref.current);
      }
    };
  }, [ref, settings]);

  const getAnimationClass = () => {
    if (!settings.animations_enabled || !settings.scroll_animations) {
      return '';
    }

    const speedClass = {
      fast: 'duration-300',
      medium: 'duration-500',
      slow: 'duration-700',
    }[settings.animation_speed || 'medium'];

    return `transition-all transform ${speedClass} ${
      isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'
    }`;
  };

  return { ref, isVisible, getAnimationClass };
};
