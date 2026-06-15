import { useEffect } from 'react';
import Lenis from 'lenis';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import HeroSection from '../sections/HeroSection';
import FeaturesSection from '../sections/FeaturesSection';
import AIAssistantSection from '../sections/AIAssistantSection';
import SVGStrokeSection from '../sections/SVGStrokeSection';
import CropManagementSection from '../sections/CropManagementSection';
import AppShowcaseSection from '../sections/AppShowcaseSection';
import ScenariosSection from '../sections/ScenariosSection';
import DownloadSection from '../sections/DownloadSection';
import FAQSection from '../sections/FAQSection';

gsap.registerPlugin(ScrollTrigger);

export default function Home() {
  useEffect(() => {
    const lenis = new Lenis({
      lerp: 0.1,
      duration: 1.2,
    });

    lenis.on('scroll', ScrollTrigger.update);

    gsap.ticker.add((time) => {
      lenis.raf(time * 1000);
    });

    gsap.ticker.lagSmoothing(0);

    return () => {
      lenis.destroy();
    };
  }, []);

  return (
    <div>
      <HeroSection />
      <FeaturesSection />
      <ScenariosSection />
      <AIAssistantSection />
      <SVGStrokeSection />
      <CropManagementSection />
      <AppShowcaseSection />
      <DownloadSection />
      <FAQSection />
    </div>
  );
}
