"use client";

import { motion } from "framer-motion";
import { Moon, Sun } from "lucide-react";
import { useTheme } from "@/contexts/ThemeContext";

export default function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();

  return (
    <div className="fixed top-6 right-6 z-50">
      <motion.button
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        onClick={toggleTheme}
        className="bg-gray-200 hover:bg-gray-300 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-900 dark:text-yellow-300 rounded-full p-5 shadow-lg transition-colors"
        aria-label="Toggle theme"
        title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
      >
        <motion.div
          initial={false}
          animate={{ rotate: theme === "dark" ? 0 : 180 }}
          transition={{ duration: 0.3, ease: "easeInOut" }}
        >
          {theme === "dark" ? (
            <Moon size={24} />
          ) : (
            <Sun size={24} />
          )}
        </motion.div>
      </motion.button>
    </div>
  );
}