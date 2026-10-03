"use client";

import { useEffect } from "react";

type ChatbotPlan = "free" | "pro";

export function ChatbotLoader() {
  useEffect(() => {
    // Universal Animation Killer CSS (Targeting all potential launcher elements & keyframes)
    const styleId = "dfte-chatbot-custom-style";
    if (!document.getElementById(styleId)) {
      const style = document.createElement("style");
      style.id = styleId;
      style.textContent = `
        /* Force freeze anything when data-chat-active is true */
        body[data-chat-active="true"] [class*="chatbot"],
        body[data-chat-active="true"] [id*="chatbot"],
        body[data-chat-active="true"] iframe,
        body[data-chat-active="true"] button,
        body[data-chat-active="true"] img,
        body[data-chat-active="true"] svg,
        .dfte-bot-paused,
        .dfte-bot-paused * {
          animation: none !important;
          -webkit-animation: none !important;
          transform: none !important;
          transition: none !important;
        }
      `;
      document.head.appendChild(style);
    }

    const plan: ChatbotPlan =
      (localStorage.getItem("dfte_plan") as ChatbotPlan | null) ||
      (process.env.NEXT_PUBLIC_CHATBOT_PLAN as ChatbotPlan) ||
      "free";

    const base = (
      process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
    ).replace(/\/+$/, "");

    const isPro = plan === "pro";
    const folder = isPro ? "chatbot_pro" : "chatbot_free";

    const cssPath = `/${folder}/chatbot.css`;
    const scriptPath = `/${folder}/chatbot.js`;

    const w = window as typeof window & {
      DFTE_CHATBOT_API?: string;
      DFTE_PRO_CHATBOT_API?: string;
    };

    w.DFTE_CHATBOT_API = `${base}/chatbot/query`;
    w.DFTE_PRO_CHATBOT_API = `${base}/agent/query`;

    document.getElementById("dfte-chatbot-css")?.remove();
    document.getElementById("dfte-chatbot-script")?.remove();

    const link = document.createElement("link");
    link.id = "dfte-chatbot-css";
    link.rel = "stylesheet";
    link.href = cssPath;
    document.head.appendChild(link);

    const script = document.createElement("script");
    script.id = "dfte-chatbot-script";
    script.src = scriptPath;
    script.async = true;
    script.dataset.chatbotPlan = plan;

    script.onload = () => {
      console.log("Digital FTE chatbot loaded:", plan);

      // Global click/touch listener setup
      const handleGlobalClick = (e: MouseEvent | TouchEvent) => {
        const target = e.target as HTMLElement;
        if (!target) return;

        // Check if click was on chatbot launcher or close button
        const isChatbotClick =
          target.closest("#dfte-chatbot-launcher") ||
          target.closest(".chatbot-launcher") ||
          target.closest("[class*='chatbot']") ||
          target.closest("[id*='chatbot']");

        if (isChatbotClick) {
          const isActive = document.body.getAttribute("data-chat-active") === "true";
          if (!isActive) {
            document.body.setAttribute("data-chat-active", "true");
          } else {
            document.body.removeAttribute("data-chat-active");
          }
        }
      };

      window.addEventListener("click", handleGlobalClick);
      window.addEventListener("touchend", handleGlobalClick);
    };

    document.body.appendChild(script);

    return () => {
      document.getElementById("dfte-chatbot-script")?.remove();
      document.getElementById("dfte-chatbot-css")?.remove();
      document.getElementById(styleId)?.remove();
      document.body.removeAttribute("data-chat-active");
    };
  }, []);

  return null;
}