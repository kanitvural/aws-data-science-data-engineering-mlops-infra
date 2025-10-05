// app/(auth)/login/page.tsx
"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Plane,
  Mail,
  Lock,
  User,
  ArrowRight,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Chrome,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { AuthService } from "@/services/authService";
import { useAuthRedirect } from "@/hooks/useAuthRedirect";

export default function LoginPage() {
  const router = useRouter();
  const { isLoading: isCheckingAuth } = useAuthRedirect(false); // Auth check

  const [mode, setMode] = useState<"signin" | "signup" | "verify">("signin");
  const [formData, setFormData] = useState({
    email: "",
    password: "",
    name: "",
    verificationCode: "",
  });
  const [isLoading, setIsLoading] = useState(false); // Form submit loading
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  // Auth check yapılırken loading göster
  if (isCheckingAuth) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  const handleSubmit = async (e: React.FormEvent) => {
    console.log("🔥 FORM SUBMITTED!")
    e.preventDefault();
    setError("");
    setSuccess("");
    setIsLoading(true);

    try {
      if (mode === "signin") {
        console.log("🔑 Calling login with:", formData.email);
        const result = await AuthService.login({
          username: formData.email,
          password: formData.password,
        });
        console.log("✅ Login response:", result);
        setSuccess("Successfully signed in! Redirecting...");

        // window.location.href = "/"; //  hard redirect instead of router.push 
        router.push('/')


      } else if (mode === "signup") {
        await AuthService.signup({
          username: formData.email,
          password: formData.password,
          email: formData.email,
        });
        setSuccess(
          "Account created! Please check your email for verification code."
        );
        setMode("verify");
      } else if (mode === "verify") {
        await AuthService.confirmSignup({
          username: formData.email,
          code: formData.verificationCode,
        });
        setSuccess("Email verified! You can now sign in.");
        setTimeout(() => {
          setMode("signin");
          setFormData({ ...formData, verificationCode: "" });
        }, 2000);
      }
    } catch (err: any) {
      setError(err.message || "An error occurred. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-indigo-50 dark:from-gray-900 dark:via-gray-800 dark:to-gray-900 flex items-center justify-center p-4 relative overflow-hidden">
      {/* Animated Background */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <motion.div
          animate={{ rotate: [0, 360], scale: [1, 1.2, 1] }}
          transition={{ duration: 20, repeat: Infinity }}
          className="absolute -top-40 -right-40 w-96 h-96 bg-blue-400/10 rounded-full blur-3xl"
        />
        <motion.div
          animate={{ rotate: [360, 0], scale: [1, 1.3, 1] }}
          transition={{ duration: 25, repeat: Infinity }}
          className="absolute -bottom-40 -left-40 w-96 h-96 bg-indigo-400/10 rounded-full blur-3xl"
        />

        {[...Array(3)].map((_, i) => (
          <motion.div
            key={i}
            initial={{ x: -100, y: 100 + i * 150 }}
            animate={{
              x: ["0%", "100%"],
              y: [100 + i * 150, 50 + i * 150, 100 + i * 150],
            }}
            transition={{
              duration: 15 + i * 5,
              repeat: Infinity,
              ease: "linear",
            }}
            className="absolute opacity-5"
          >
            <Plane size={40} className="text-blue-600" />
          </motion.div>
        ))}
      </div>

      {/* Main Container */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        className="relative w-full max-w-6xl grid lg:grid-cols-2 gap-8 items-center"
      >
        {/* Left Side - Branding */}
        <motion.div
          initial={{ opacity: 0, x: -50 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.2, duration: 0.6 }}
          className="hidden lg:block space-y-8 p-8"
        >
          <div className="space-y-4">
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ delay: 0.4, type: "spring", stiffness: 200 }}
              className="flex items-center space-x-3"
            >
              <div className="p-3 bg-gradient-to-br from-blue-600 to-indigo-600 rounded-2xl shadow-lg">
                <Plane size={40} className="text-white" />
              </div>
              <h1 className="text-4xl font-bold text-gray-900 dark:text-white">
                FlightAI
              </h1>
            </motion.div>

            <h2 className="text-5xl font-bold text-gray-900 dark:text-white leading-tight">
              Real-Time Flight
              <span className="block text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-indigo-600">
                Delay Prediction
              </span>
            </h2>

            <p className="text-xl text-gray-600 dark:text-gray-400">
              AWS SageMaker ML Pipeline • DynamoDB Stream • WebSocket Live • AWS
              Bedrock AI Assistant
            </p>
          </div>

          <div className="space-y-4">
            {[
              {
                icon: "🚀",
                text: "Real-time ML predictions with AWS SageMaker",
              },
              { icon: "💬", text: "AI-powered chatbot with AWS Bedrock" },
              { icon: "🔐", text: "Secure authentication with AWS Cognito" },
              { icon: "📊", text: "Live dashboard with WebSocket streaming" },
            ].map((feature, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.6 + i * 0.1 }}
                className="flex items-center space-x-3 p-4 bg-white/50 dark:bg-gray-800/50 backdrop-blur-sm rounded-xl border border-gray-200 dark:border-gray-700"
              >
                <span className="text-2xl">{feature.icon}</span>
                <span className="text-gray-700 dark:text-gray-300">
                  {feature.text}
                </span>
              </motion.div>
            ))}
          </div>
        </motion.div>

        {/* Right Side - Auth Form */}
        <motion.div
          initial={{ opacity: 0, x: 50 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.3, duration: 0.6 }}
          className="relative"
        >
          <div className="bg-white dark:bg-gray-800 rounded-3xl shadow-2xl p-8 border border-gray-100 dark:border-gray-700">
            {/* Mobile Logo */}
            <div className="lg:hidden flex items-center justify-center mb-6">
              <div className="p-2 bg-gradient-to-br from-blue-600 to-indigo-600 rounded-xl">
                <Plane size={32} className="text-white" />
              </div>
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white ml-3">
                FlightAI
              </h1>
            </div>

            {/* Tab Switcher */}
            {mode !== "verify" && (
              <div className="flex space-x-2 mb-6 p-1 bg-gray-100 dark:bg-gray-700 rounded-xl">
                <button
                  onClick={() => setMode("signin")}
                  className={`flex-1 py-3 px-4 rounded-lg font-medium transition-all ${
                    mode === "signin"
                      ? "bg-white dark:bg-gray-800 text-blue-600 shadow-md"
                      : "text-gray-600 dark:text-gray-400 hover:text-gray-900"
                  }`}
                >
                  Sign In
                </button>
                <button
                  onClick={() => setMode("signup")}
                  className={`flex-1 py-3 px-4 rounded-lg font-medium transition-all ${
                    mode === "signup"
                      ? "bg-white dark:bg-gray-800 text-blue-600 shadow-md"
                      : "text-gray-600 dark:text-gray-400 hover:text-gray-900"
                  }`}
                >
                  Sign Up
                </button>
              </div>
            )}

            {/* Title */}
            <div className="mb-6">
              <h3 className="text-2xl font-bold text-gray-900 dark:text-white">
                {mode === "signin" && "Welcome back"}
                {mode === "signup" && "Create your account"}
                {mode === "verify" && "Verify your email"}
              </h3>
              <p className="text-gray-600 dark:text-gray-400 mt-1">
                {mode === "signin" && "Sign in to access your flight dashboard"}
                {mode === "signup" &&
                  "Join us to start predicting flight delays"}
                {mode === "verify" && "Enter the code sent to your email"}
              </p>
            </div>

            {/* Alerts */}
            <AnimatePresence>
              {error && (
                <motion.div
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  className="mb-4 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl flex items-center space-x-2"
                >
                  <AlertCircle className="text-red-600" size={20} />
                  <span className="text-red-700 dark:text-red-300 text-sm">
                    {error}
                  </span>
                </motion.div>
              )}

              {success && (
                <motion.div
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  className="mb-4 p-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-xl flex items-center space-x-2"
                >
                  <CheckCircle2 className="text-green-600" size={20} />
                  <span className="text-green-700 dark:text-green-300 text-sm">
                    {success}
                  </span>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Form Fields */}
            <form onSubmit={handleSubmit} className="space-y-4">
              <AnimatePresence mode="wait">
                {mode !== "verify" && (
                  <motion.div key="email">
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Email Address
                    </label>
                    <div className="relative">
                      <Mail
                        className="absolute left-4 top-1/2 transform -translate-y-1/2 text-gray-400"
                        size={20}
                      />
                      <input
                        type="email"
                        required
                        value={formData.email}
                        onChange={(e) =>
                          setFormData({ ...formData, email: e.target.value })
                        }
                        className="w-full pl-12 pr-4 py-3 border border-gray-300 dark:border-gray-600 rounded-xl focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                        placeholder="your@email.com"
                      />
                    </div>
                  </motion.div>
                )}

                {mode !== "verify" && (
                  <motion.div key="password">
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Password
                    </label>
                    <div className="relative">
                      <Lock
                        className="absolute left-4 top-1/2 transform -translate-y-1/2 text-gray-400"
                        size={20}
                      />
                      <input
                        type={showPassword ? "text" : "password"}
                        required
                        value={formData.password}
                        onChange={(e) =>
                          setFormData({ ...formData, password: e.target.value })
                        }
                        className="w-full pl-12 pr-12 py-3 border border-gray-300 dark:border-gray-600 rounded-xl focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                        placeholder="••••••••"
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute right-4 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-600"
                      >
                        {showPassword ? "👁️" : "👁️‍🗨️"}
                      </button>
                    </div>
                  </motion.div>
                )}

                {mode === "verify" && (
                  <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Verification Code
                    </label>
                    <input
                      type="text"
                      required
                      value={formData.verificationCode}
                      onChange={(e) =>
                        setFormData({
                          ...formData,
                          verificationCode: e.target.value,
                        })
                      }
                      className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-xl focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-center text-2xl tracking-widest"
                      placeholder="123456"
                      maxLength={6}
                    />
                  </motion.div>
                )}
              </AnimatePresence>

              {mode === "signin" && (
                <div className="flex items-center justify-between text-sm">
                  <label className="flex items-center text-gray-600 dark:text-gray-400">
                    <input type="checkbox" className="mr-2 rounded" />
                    Remember me
                  </label>
                  <button
                    type="button"
                    className="text-blue-600 hover:text-blue-700 font-medium"
                  >
                    Forgot password?
                  </button>
                </div>
              )}

              <button
                type="submit"
                disabled={isLoading}
                className="w-full bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white font-semibold py-3 px-6 rounded-xl transition-all transform hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none shadow-lg flex items-center justify-center space-x-2"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="animate-spin" size={20} />
                    <span>Processing...</span>
                  </>
                ) : (
                  <>
                    <span>
                      {mode === "signin" && "Sign In"}
                      {mode === "signup" && "Create Account"}
                      {mode === "verify" && "Verify Email"}
                    </span>
                    <ArrowRight size={20} />
                  </>
                )}
              </button>
            </form>

            {/* Google Sign In */}
            {mode !== "verify" && (
              <>
                <div className="relative my-6">
                  <div className="absolute inset-0 flex items-center">
                    <div className="w-full border-t border-gray-300 dark:border-gray-600"></div>
                  </div>
                  <div className="relative flex justify-center text-sm">
                    <span className="px-4 bg-white dark:bg-gray-800 text-gray-500">
                      Or continue with
                    </span>
                  </div>
                </div>

                <button
                  type="button"
                  className="w-full border-2 border-gray-300 dark:border-gray-600 hover:border-gray-400 text-gray-700 dark:text-gray-300 font-medium py-3 px-6 rounded-xl transition-all hover:bg-gray-50 dark:hover:bg-gray-700 flex items-center justify-center space-x-2"
                >
                  <Chrome size={20} className="text-blue-600" />
                  <span>Sign in with Google</span>
                </button>
              </>
            )}
          </div>

          <p className="text-center text-sm text-gray-600 dark:text-gray-400 mt-6">
            {mode === "signin"
              ? "Don't have an account? "
              : mode === "verify"
              ? "Back to "
              : "Already have an account? "}
            <button
              onClick={() => setMode(mode === "signin" ? "signup" : "signin")}
              className="text-blue-600 hover:text-blue-700 font-semibold"
            >
              {mode === "signin" ? "Sign up" : "Sign in"}
            </button>
          </p>
        </motion.div>
      </motion.div>
    </div>
  );
}
