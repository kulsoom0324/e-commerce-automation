"use client";

import { useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useLanguage } from "../lib/LanguageContext";
import { TrendingUp } from "lucide-react";

export function LanguageSelectorModal() {
  const { showLanguageModal, setLanguage, closeLanguageModal } = useLanguage();

  const handleSelect = (lang: "en" | "ur") => {
    setLanguage(lang);
    closeLanguageModal();
  };

  // Close on ESC key press
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeLanguageModal();
    };
    if (showLanguageModal) {
      window.addEventListener("keydown", handleKeyDown);
    }
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [showLanguageModal, closeLanguageModal]);

  return (
    <AnimatePresence>
      {showLanguageModal && (
        <motion.div
          key="lang-modal-backdrop"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.3 }}
          onClick={closeLanguageModal}
          className="fixed inset-0 z-[9999] flex items-center justify-center p-4 cursor-pointer"
          style={{
            background:
              "radial-gradient(ellipse at center, rgba(2,4,13,0.97) 0%, rgba(4,9,15,0.99) 100%)",
          }}
          role="dialog"
          aria-modal="true"
          aria-labelledby="language-modal-title"
        >
          {/* Animated background glows */}
          <div className="absolute inset-0 overflow-hidden pointer-events-none">
            <motion.div
              className="absolute -top-40 left-1/2 -translate-x-1/2 w-[700px] h-[700px] rounded-full"
              style={{
                background:
                  "radial-gradient(circle, rgba(245,158,11,0.15) 0%, transparent 70%)",
              }}
              animate={{ scale: [1, 1.1, 1], opacity: [0.5, 0.8, 0.5] }}
              transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
            />
            <div
              className="absolute bottom-0 right-0 w-[400px] h-[400px] rounded-full"
              style={{
                background:
                  "radial-gradient(circle, rgba(139,92,246,0.08) 0%, transparent 70%)",
              }}
            />
            {/* Dot grid */}
            <div
              className="absolute inset-0 opacity-[0.07]"
              style={{
                backgroundImage:
                  "radial-gradient(rgba(251,191,36,0.6) 1px, transparent 1px)",
                backgroundSize: "32px 32px",
              }}
            />
          </div>

          {/* Modal Card */}
          <motion.div
            key="lang-modal-card"
            initial={{ opacity: 0, scale: 0.88, y: 24 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.92, y: 16 }}
            transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
            onClick={(e) => e.stopPropagation()}
            className="relative w-full max-w-md cursor-default"
          >
            {/* Glow ring behind card */}
            <div className="absolute inset-0 rounded-3xl bg-amber-400/10 blur-2xl scale-105 pointer-events-none" />

            <div className="relative rounded-3xl border border-white/10 bg-[#06111d]/95 backdrop-blur-2xl shadow-2xl shadow-black/50 overflow-hidden">
              {/* Top amber accent bar */}
              <div className="h-1 w-full bg-gradient-to-r from-amber-500 via-yellow-400 to-orange-500" />

              <div className="p-8 sm:p-10">
                {/* Logo */}
                <div className="flex items-center justify-center gap-3 mb-8">
                  <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-amber-500 to-yellow-400 flex items-center justify-center shadow-lg shadow-amber-500/30">
                    <TrendingUp className="w-6 h-6 text-[#06111b]" />
                  </div>
                  <div>
                    <p className="text-xl font-extrabold text-white tracking-tight">
                      Digital FTE
                    </p>
                    <p className="text-[10px] font-bold text-amber-300 tracking-widest uppercase">
                      AI E-Commerce Employee
                    </p>
                  </div>
                </div>

                {/* Divider */}
                <div className="w-16 h-px bg-gradient-to-r from-transparent via-amber-400/40 to-transparent mx-auto mb-8" />

                {/* Title (bilingual) */}
                <div className="text-center mb-2" id="language-modal-title">
                  <p className="text-lg font-bold text-white">
                    Select Your Language
                  </p>
                  <p
                    className="text-base font-semibold text-amber-200/80 mt-1"
                    dir="rtl"
                  >
                    اپنی زبان منتخب کریں
                  </p>
                </div>

                <p className="text-center text-xs text-slate-400 mb-8">
                  Your choice will be remembered for future visits
                </p>

                {/* Language Buttons */}
                <div className="grid grid-cols-2 gap-4">
                  {/* English Button */}
                  <motion.button
                    type="button"
                    whileHover={{ scale: 1.03, y: -2 }}
                    whileTap={{ scale: 0.97 }}
                    onClick={() => handleSelect("en")}
                    className="group relative flex flex-col items-center gap-3 p-6 rounded-2xl border border-white/10 bg-white/5 hover:border-amber-400/50 hover:bg-amber-400/5 transition-all duration-300 cursor-pointer"
                  >
                    <div className="text-4xl">🇬🇧</div>
                    <div className="text-center">
                      <p className="text-sm font-extrabold text-white group-hover:text-amber-300 transition-colors">
                        English
                      </p>
                      <p className="text-[10px] text-slate-400 mt-0.5">
                        English
                      </p>
                    </div>
                    <div className="absolute inset-0 rounded-2xl bg-amber-400/0 group-hover:bg-amber-400/5 transition-colors duration-300 pointer-events-none" />
                  </motion.button>

                  {/* Urdu Button */}
                  <motion.button
                    type="button"
                    whileHover={{ scale: 1.03, y: -2 }}
                    whileTap={{ scale: 0.97 }}
                    onClick={() => handleSelect("ur")}
                    className="group relative flex flex-col items-center gap-3 p-6 rounded-2xl border border-white/10 bg-white/5 hover:border-amber-400/50 hover:bg-amber-400/5 transition-all duration-300 cursor-pointer"
                    dir="rtl"
                  >
                    <div className="text-4xl">🇵🇰</div>
                    <div className="text-center">
                      <p className="text-sm font-extrabold text-white group-hover:text-amber-300 transition-colors">
                        اردو
                      </p>
                      <p className="text-[10px] text-slate-400 mt-0.5">
                        Urdu
                      </p>
                    </div>
                    <div className="absolute inset-0 rounded-2xl bg-amber-400/0 group-hover:bg-amber-400/5 transition-colors duration-300 pointer-events-none" />
                  </motion.button>
                </div>

                {/* Bottom note */}
                <p className="text-center text-[10px] text-slate-500 mt-6">
                  You can change language anytime from the navbar •{" "}
                  <span dir="rtl">آپ کسی بھی وقت زبان تبدیل کر سکتے ہیں</span>
                </p>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}