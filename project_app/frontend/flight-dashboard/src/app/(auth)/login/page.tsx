"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Plane,
  Mail,
  Lock,
  ArrowRight,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Chrome,
  Check,
  X,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { RestApiService } from "@/services/restApiService";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<
    "signin" | "signup" | "verify" | "forgot" | "reset"
  >("signin");

  const [formData, setFormData] = useState({
    email: "",
    password: "",
    firstName: "",
    lastName: "",
    gender: "",
    verificationCode: "",
  });

  const [passwordValidation, setPasswordValidation] = useState({
    length: false,
    uppercase: false,
    lowercase: false,
    number: false,
    symbol: false,
  });

  const validatePassword = (password: string) => {
    const validations = {
      length: password.length >= 8,
      uppercase: /[A-Z]/.test(password),
      lowercase: /[a-z]/.test(password),
      number: /[0-9]/.test(password),
      symbol: /[^A-Za-z0-9]/.test(password),
    };
    setPasswordValidation(validations);
  };

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isPasswordFocused, setIsPasswordFocused] = useState(false);
  const [isResendingCode, setIsResendingCode] = useState(false);

  // Name validation states
  const [nameErrors, setNameErrors] = useState({
    firstName: "",
    lastName: "",
  });

  function capitalize(word: string): string {
    if (!word) return "";
    return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
  }

  // Validate names
  const validateName = (name: string, field: "firstName" | "lastName") => {
    if (name.length > 0 && name.length < 2) {
      setNameErrors((prev) => ({
        ...prev,
        [field]: "Must be at least 2 characters",
      }));
      return false;
    } else {
      setNameErrors((prev) => ({
        ...prev,
        [field]: "",
      }));
      return true;
    }
  };

  // Check if all password requirements are met
  const isPasswordValid = Object.values(passwordValidation).every(
    (valid) => valid
  );

  // Check if names are valid
  const isNamesValid =
    formData.firstName.length >= 2 && formData.lastName.length >= 2;

  // Check if signup form is valid
  const isSignupFormValid =
    mode !== "signup" ||
    (formData.email &&
      formData.password &&
      isPasswordValid &&
      isNamesValid &&
      formData.gender);


  // Resend verification code
  const handleResendCode = async () => {
    if (!formData.email) {
      setError("Username is required to resend the verification code.");
      return;
    }

    setIsResendingCode(true);
    setError("");
    setSuccess("");

    try {
      await RestApiService.resendConfirmation(formData.email);

      setSuccess("Verification code resent! Please check your email.");
    } catch (err: any) {
      setError(
        err.message || "Failed to resend verification code. Please try again."
      );
    } finally {
      setIsResendingCode(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccess("");

    // Additional validation for signup
    if (mode === "signup") {
      if (!isPasswordValid) {
        setError("Please meet all password requirements");
        return;
      }
      if (!isNamesValid) {
        setError("First and last names must be at least 2 characters");
        return;
      }
    }

    setIsLoading(true);

    try {
      if (mode === "signin") {
        await RestApiService.login({
          username: formData.email,
          password: formData.password,
        });

        // ✅ Retrieve user name and save it to the session storage
        type CognitoAttr = { Name: string; Value?: string };
        type GetUserResponse = { user?: { UserAttributes?: CognitoAttr[] } };

        const userResp =
          (await RestApiService.getCurrentUser()) as GetUserResponse;
        const attrs: CognitoAttr[] = userResp.user?.UserAttributes ?? [];

        const findValue = (name: string) =>
          attrs.find((a) => a.Name === name)?.Value;
        const firstName =
          findValue("given_name") ?? findValue("first_name") ?? "";

        if (firstName) {
          sessionStorage.setItem("userFirstName", firstName);
        } else {
          console.warn("firstName bulunamadı, attrs:", attrs);
        }

        setSuccess("Successfully signed in! Redirecting...");
        setTimeout(() => router.push("/"), 1000);
      } else if (mode === "signup") {
        await RestApiService.signup({
          username: formData.email,
          password: formData.password,
          email: formData.email,
          firstName: capitalize(formData.firstName),
          lastName: capitalize(formData.lastName),
          gender: formData.gender,
        });
        setSuccess(
          "Account created! Please check your email for verification code."
        );
        setMode("verify");
      } else if (mode === "verify") {
        await RestApiService.confirmSignup({
          username: formData.email,
          code: formData.verificationCode,
        });
        setSuccess("Email verified! You can now sign in.");
        setTimeout(() => {
          setMode("signin");
          setFormData({ ...formData, verificationCode: "" });
        }, 2000);
      } else if (mode === "forgot") {
        await RestApiService.forgotPassword(formData.email);
        setSuccess("Reset code sent to your email!");
        setMode("reset");
      } else if (mode === "reset") {
        await RestApiService.confirmForgotPassword({
          username: formData.email,
          code: formData.verificationCode,
          newPassword: formData.password,
        });
        setSuccess("Password reset successful! You can now sign in.");
        setMode("signin");
      }
    } catch (err: any) {
      setError(err.message || "An error occurred. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  const features = [
    {
      icon: "🚀",
      text: "Real-time ML predictions with AWS SageMaker Endpoint",
    },
    { icon: "💬", text: "AI-powered chatbot with AWS Bedrock-Agentcore" },
    { icon: "🔐", text: "Secure authentication with AWS Cognito" },
    { icon: "📊", text: "Live dashboard with WebSocket streaming" },
  ];

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
      </div>

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
          className="space-y-8 p-8"
        >
          {/* Logo */}
          <div className="flex items-center space-x-3">
            <div className="p-3 bg-gradient-to-br from-blue-600 to-indigo-600 rounded-2xl shadow-lg">
              <Plane size={40} className="text-white" />
            </div>
            <h1 className="text-4xl font-bold text-gray-900 dark:text-white">
              FlightAI
            </h1>
          </div>

          {/* Titles */}
          <h2 className="text-5xl font-bold text-gray-900 dark:text-white leading-tight">
            Real-Time Flight
            <span className="block text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-indigo-600">
              Delay Prediction
            </span>
          </h2>

          <p className="text-xl text-gray-600 dark:text-gray-400">
            Ultimate AWS AI Project ✈️ Data Engineering • Data Science • MLOps •
            Multi-Agent-Chatbot • Real-Time Web App
          </p>

          {/* Features */}
          <div className="space-y-4">
            {features.map((feature, i) => (
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

            {/* Tab Switcher - Hidden in verify, forgot, reset modes */}
            {mode !== "verify" && mode !== "forgot" && mode !== "reset" && (
              <div className="flex space-x-2 mb-6 p-1 bg-gray-100 dark:bg-gray-700 rounded-xl">
                <button
                  onClick={() => {
                    setMode("signin");
                    setError("");
                    setSuccess("");
                  }}
                  className={`flex-1 py-3 px-4 rounded-lg font-medium transition-all ${
                    mode === "signin"
                      ? "bg-white dark:bg-gray-800 text-blue-600 shadow-md"
                      : "text-gray-600 dark:text-gray-400 hover:text-gray-900"
                  }`}
                >
                  Sign In
                </button>
                <button
                  onClick={() => {
                    setMode("signup");
                    setError("");
                    setSuccess("");
                  }}
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

            {/* Title & Subtitle */}
            <div className="mb-6">
              <h3 className="text-2xl font-bold text-gray-900 dark:text-white">
                {mode === "signin" && "Welcome back"}
                {mode === "signup" && "Create your account"}
                {mode === "verify" && "Verify your email"}
                {mode === "forgot" && "Forgot Password"}
                {mode === "reset" && "Reset Password"}
              </h3>
              <p className="text-gray-600 dark:text-gray-400 mt-1">
                {mode === "signin" && "Sign in to access your flight dashboard"}
                {mode === "signup" &&
                  "Join us to start predicting flight delays"}
                {mode === "verify" && "Enter the code sent to your email"}
                {mode === "forgot" && "Enter your email to reset your password"}
                {mode === "reset" && "Enter the reset code and new password"}
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

            {/* Form */}
            <form onSubmit={handleSubmit} className="space-y-4">
              <AnimatePresence mode="wait">
                {/* Email */}
                {(mode === "signin" ||
                  mode === "signup" ||
                  mode === "forgot" ||
                  mode === "reset") && (
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

                {/* Password for Sign In / Sign Up only */}
                {(mode === "signin" || mode === "signup") && (
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
                        onFocus={() =>
                          mode === "signup" && setIsPasswordFocused(true)
                        }
                        onBlur={() => setIsPasswordFocused(false)}
                        onChange={(e) => {
                          setFormData({
                            ...formData,
                            password: e.target.value,
                          });
                          if (mode === "signup") {
                            validatePassword(e.target.value);
                          }
                        }}
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

                    {/* Password Requirements - Only show in signup mode when focused */}
                    {mode === "signup" && isPasswordFocused && (
                      <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: "auto" }}
                        exit={{ opacity: 0, height: 0 }}
                        className="mt-3 p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg border border-gray-200 dark:border-gray-600"
                      >
                        <p className="text-xs font-medium text-gray-700 dark:text-gray-300 mb-2">
                          Password must contain:
                        </p>
                        <div className="space-y-1">
                          <PasswordRequirement
                            met={passwordValidation.length}
                            text="At least 8 characters"
                          />
                          <PasswordRequirement
                            met={passwordValidation.uppercase}
                            text="One uppercase letter"
                          />
                          <PasswordRequirement
                            met={passwordValidation.lowercase}
                            text="One lowercase letter"
                          />
                          <PasswordRequirement
                            met={passwordValidation.number}
                            text="One number"
                          />
                          <PasswordRequirement
                            met={passwordValidation.symbol}
                            text="One special character"
                          />
                        </div>
                      </motion.div>
                    )}
                  </motion.div>
                )}

                {/* First Name */}
                {mode === "signup" && (
                  <motion.div key="firstName">
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      First Name
                    </label>
                    <input
                      type="text"
                      required
                      value={formData.firstName}
                      onChange={(e) => {
                        setFormData({ ...formData, firstName: e.target.value });
                        validateName(e.target.value, "firstName");
                      }}
                      className={`w-full px-4 py-3 border ${
                        nameErrors.firstName
                          ? "border-red-500 dark:border-red-500"
                          : "border-gray-300 dark:border-gray-600"
                      } rounded-xl focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white`}
                      placeholder="John"
                    />
                    {nameErrors.firstName && (
                      <p className="mt-1 text-xs text-red-600 dark:text-red-400">
                        {nameErrors.firstName}
                      </p>
                    )}
                  </motion.div>
                )}

                {/* Last Name */}
                {mode === "signup" && (
                  <motion.div key="lastName">
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Last Name
                    </label>
                    <input
                      type="text"
                      required
                      value={formData.lastName}
                      onChange={(e) => {
                        setFormData({ ...formData, lastName: e.target.value });
                        validateName(e.target.value, "lastName");
                      }}
                      className={`w-full px-4 py-3 border ${
                        nameErrors.lastName
                          ? "border-red-500 dark:border-red-500"
                          : "border-gray-300 dark:border-gray-600"
                      } rounded-xl focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white`}
                      placeholder="Doe"
                    />
                    {nameErrors.lastName && (
                      <p className="mt-1 text-xs text-red-600 dark:text-red-400">
                        {nameErrors.lastName}
                      </p>
                    )}
                  </motion.div>
                )}

                {/* Gender */}
                {mode === "signup" && (
                  <motion.div key="gender">
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Gender
                    </label>
                    <select
                      required
                      value={formData.gender}
                      onChange={(e) =>
                        setFormData({ ...formData, gender: e.target.value })
                      }
                      className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-xl focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    >
                      <option value="" disabled>
                        Select gender
                      </option>
                      <option value="male">Male</option>
                      <option value="female">Female</option>
                      <option value="other">Other</option>
                    </select>
                  </motion.div>
                )}

                {/* Verification Code for Verify */}
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

                    {/* Resend Code Button */}
                    <div className="mt-3 text-center">
                      <button
                        type="button"
                        onClick={handleResendCode}
                        disabled={isResendingCode}
                        className="text-sm text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300 font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center mx-auto"
                      >
                        {isResendingCode ? (
                          <>
                            <Loader2 className="animate-spin mr-2" size={14} />
                            Sending...
                          </>
                        ) : (
                          "Didn't receive code? Resend"
                        )}
                      </button>
                    </div>
                  </motion.div>
                )}

                {/* Reset Password Mode */}
                {mode === "reset" && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    key="reset-code"
                  >
                    {/* Reset Code */}
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Reset Code
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

                    {/* New Password */}
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 mt-4">
                      New Password
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
              </AnimatePresence>

              {/* Forgot password link */}
              {mode === "signin" && (
                <div className="flex items-center justify-between text-sm">
                  <label className="flex items-center text-gray-600 dark:text-gray-400">
                    <input type="checkbox" className="mr-2 rounded" />
                    Remember me
                  </label>
                  <button
                    type="button"
                    onClick={() => setMode("forgot")}
                    className="text-blue-600 hover:text-blue-700 font-medium"
                  >
                    Forgot password?
                  </button>
                </div>
              )}

              {/* Submit Button */}
              <button
                type="submit"
                disabled={isLoading || !isSignupFormValid}
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
                      {mode === "forgot" && "Send Reset Code"}
                      {mode === "reset" && "Reset Password"}
                    </span>
                    <ArrowRight size={20} />
                  </>
                )}
              </button>
            </form>
          </div>

          <p className="text-center text-sm text-gray-600 dark:text-gray-400 mt-6">
            {mode === "signin" && (
              <>
                Don't have an account?{" "}
                <button
                  onClick={() => {
                    setMode("signup");
                    setError("");
                    setSuccess("");
                  }}
                  className="text-blue-600 hover:text-blue-700 font-semibold"
                >
                  Sign up
                </button>
              </>
            )}
            {mode === "signup" && (
              <>
                Already have an account?{" "}
                <button
                  onClick={() => {
                    setMode("signin");
                    setError("");
                    setSuccess("");
                  }}
                  className="text-blue-600 hover:text-blue-700 font-semibold"
                >
                  Sign in
                </button>
              </>
            )}
            {(mode === "verify" || mode === "forgot" || mode === "reset") && (
              <>
                Back to{" "}
                <button
                  onClick={() => {
                    setMode("signin");
                    setError("");
                    setSuccess("");
                    // Clear verification and reset data
                    setFormData({
                      ...formData,
                      verificationCode: "",
                      password: mode === "reset" ? "" : formData.password,
                    });
                  }}
                  className="text-blue-600 hover:text-blue-700 font-semibold"
                >
                  Sign in
                </button>
              </>
            )}
          </p>
        </motion.div>
      </motion.div>
    </div>
  );
}

// Password Requirement Component
function PasswordRequirement({ met, text }: { met: boolean; text: string }) {
  return (
    <div className="flex items-center space-x-2">
      <div
        className={`flex-shrink-0 w-4 h-4 rounded-full flex items-center justify-center ${
          met
            ? "bg-green-500 dark:bg-green-600"
            : "bg-gray-300 dark:bg-gray-600"
        }`}
      >
        {met ? (
          <Check size={12} className="text-white" />
        ) : (
          <X size={12} className="text-gray-500 dark:text-gray-400" />
        )}
      </div>
      <span
        className={`text-xs ${
          met
            ? "text-green-700 dark:text-green-400 font-medium"
            : "text-gray-600 dark:text-gray-400"
        }`}
      >
        {text}
      </span>
    </div>
  );
}
