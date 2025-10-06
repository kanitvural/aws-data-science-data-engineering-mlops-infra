// components/FlightGrid.tsx
"use client";

import { motion, AnimatePresence } from "framer-motion";
import { FlightTableData } from "@/types/flight";
import { format } from "date-fns";

interface FlightGridProps {
  data: FlightTableData[];
}

export default function FlightGrid({ data }: FlightGridProps) {

  const displayData = [...data];
  while (displayData.length < 12) {
    displayData.push(null as any);
  }
  const slots = displayData.slice(0, 12);

  const formatTime = (timeString: string) => {
    try {
      return format(new Date(timeString), "HH:mm");
    } catch {
      return timeString;
    }
  };

  const getDelayColor = (delay: number | null) => {
    if (delay === null) return "text-gray-400";
    if (delay <= 0) return "text-green-600";
    if (delay <= 15) return "text-yellow-600";
    return "text-red-600";
  };

  const getCarrierColor = (carrier: string) => {
    const colors = {
      AA: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
      DL: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
      UA: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
      WN: "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200",
      AS: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
    };
    return (
      colors[carrier as keyof typeof colors] ||
      "bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200"
    );
  };

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg overflow-hidden">
      <div className="px-6 py-4 bg-gradient-to-r from-blue-600 to-blue-700 dark:from-blue-700 dark:to-blue-800 text-white">
        <h2 className="text-2xl font-bold">Real-Time Flights Dashboard</h2>
        <p className="text-blue-100 dark:text-blue-200 mt-1">
          Ultimate AWS AI Project ✈️ Data Engineering • Data Science
          • MLOps • LLM • Real-Time Web App
        </p>
      </div>

      {/* Header */}
      <div className="bg-gray-50 dark:bg-gray-700 px-4 py-3 grid grid-cols-8 gap-4 text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
        <div>Flight</div>
        <div>Route</div>
        <div>Departure</div>
        <div>Arrival</div>
        <div>Aircraft</div>
        <div>Weather</div>
        <div>Delay</div>
        <div>Status</div>
      </div>

      {/* 12 Slot with Improved Animations */}
      <div className="divide-y divide-gray-200 dark:divide-gray-700">
        <AnimatePresence mode="popLayout">
          {slots.map((flight, index) => (
            <motion.div
              key={flight?.id || `empty-${index}`}
              layout
              initial={{ opacity: 0, scale: 0.95, y: -8 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.98, y: -5 }}
              transition={{
                duration: 0.15,
                ease: [0.25, 0.46, 0.45, 0.94],
              }}
              className="relative overflow-hidden min-h-[80px]"
              style={{
                transformOrigin: "center",
                willChange: "transform, opacity",
              }}
            >
              {flight ? (
                <div
                  className={`grid grid-cols-8 gap-4 px-4 py-4 hover:bg-gray-50 dark:hover:bg-gray-700 border-l-4 transition-all duration-200 ${
                    flight.dep_delay === null
                      ? "border-l-yellow-400"
                      : "border-l-green-400"
                  }`}
                >
                  {/* Flight */}
                  <div className="flex flex-col">
                    <div className="flex items-center">
                      <motion.span
                        initial={{ scale: 0.95, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                        transition={{ delay: 0.02, duration: 0.1 }}
                        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getCarrierColor(
                          flight.carrier
                        )}`}
                      >
                        {flight.carrier}
                      </motion.span>
                      <span className="ml-3 text-sm font-medium text-gray-900 dark:text-white">
                        {flight.flight}
                      </span>
                    </div>
                    <div className="text-xs text-gray-500 dark:text-gray-400 mt-1 capitalize">
                      {flight.airline?.replace(/_/g, " ") || "Unknown"}
                    </div>
                  </div>

                  {/* Route */}
                  <div>
                    <div className="text-sm font-medium text-gray-900 dark:text-white">
                      {flight.origin} → {flight.dest}
                    </div>
                    <div className="text-xs text-gray-500 dark:text-gray-400">
                      {Math.round(flight.distance)}mi •{" "}
                      {Math.round(flight.air_time)}min
                    </div>
                  </div>

                  {/* Departure */}
                  <div>
                    <div className="text-sm text-gray-900 dark:text-white">
                      <span className="font-medium">
                        {formatTime(flight.dep_time)}
                      </span>
                      <span className="text-gray-400 dark:text-gray-500 ml-1">
                        (sched: {formatTime(flight.sched_dep_time)})
                      </span>
                    </div>
                  </div>

                  {/* Arrival */}
                  <div>
                    <div className="text-sm text-gray-900 dark:text-white">
                      <span className="font-medium">
                        {formatTime(flight.arr_time)}
                      </span>
                      <span className="text-gray-400 dark:text-gray-500 ml-1">
                        (sched: {formatTime(flight.sched_arr_time)})
                      </span>
                    </div>
                    <motion.div
                      initial={{ opacity: 0, y: 3 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.05, duration: 0.15 }} // Hızlı
                      className={`text-xs ${getDelayColor(flight.arr_delay)}`}
                    >
                      {flight.arr_delay > 0
                        ? `+${flight.arr_delay}min`
                        : `${flight.arr_delay}min`}
                    </motion.div>
                  </div>

                  {/* Aircraft */}
                  <div>
                    <div className="text-sm font-medium text-gray-900 dark:text-white">
                      {flight.tailnum}
                    </div>
                    <div className="text-xs text-gray-500 dark:text-gray-400">
                      {flight.hour}:{flight.minute.toString().padStart(2, "0")}
                    </div>
                  </div>

                  {/* Weather */}
                  <div>
                    <div className="text-sm text-gray-900 dark:text-white">
                      {Math.round(flight.temp)}°F
                    </div>
                    <div className="text-xs text-gray-500 dark:text-gray-400">
                      {Math.round(flight.humid)}% •{" "}
                      {Math.round(flight.wind_speed)}mph
                    </div>
                  </div>

                  {/* Delay */}
                  <div>
                    <motion.div
                      initial={{ scale: 0.95, opacity: 0 }}
                      animate={{ scale: 1, opacity: 1 }}
                      transition={{
                        delay: 0.08,
                        duration: 0.2,
                        type: "spring",
                        stiffness: 300,
                        damping: 25,
                      }}
                      className={`text-lg font-bold ${getDelayColor(
                        flight.dep_delay
                      )}`}
                    >
                      {flight.dep_delay === null
                        ? "--"
                        : flight.dep_delay > 0
                        ? `+${flight.dep_delay}`
                        : flight.dep_delay}
                      min
                    </motion.div>
                  </div>

                  {/* Status */}
                  <div>
                    {flight.dep_delay === null ? (
                      <motion.div
                        animate={{ opacity: [1, 0.7, 1] }}
                        transition={{ repeat: Infinity, duration: 1.5 }} // Daha hızlı
                        className="flex items-center text-yellow-600 dark:text-yellow-400"
                      >
                        <motion.div
                          animate={{ scale: [1, 1.1, 1] }}
                          transition={{ repeat: Infinity, duration: 1.5 }}
                          className="w-3 h-3 bg-yellow-400 rounded-full mr-2"
                        ></motion.div>
                        <span className="text-sm font-medium">
                          Ready for Departure
                        </span>
                      </motion.div>
                    ) : (
                      <motion.div
                        initial={{ scale: 0.95, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                        transition={{
                          delay: 0.1,
                          type: "spring",
                          stiffness: 400,
                          damping: 25,
                          duration: 0.25,
                        }}
                        className="flex items-center text-green-600 dark:text-green-400"
                      >
                        <motion.div
                          initial={{ scale: 0 }}
                          animate={{ scale: 1 }}
                          transition={{
                            delay: 0.12,
                            type: "spring",
                            stiffness: 500,
                            duration: 0.2,
                          }}
                          className="w-3 h-3 bg-green-400 rounded-full mr-2"
                        ></motion.div>
                        <span className="text-sm font-medium">Departed</span>
                      </motion.div>
                    )}
                  </div>
                </div>
              ) : (
                // Empty slot Improved skeleton
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 0.3 }}
                  exit={{ opacity: 0 }}
                  className="grid grid-cols-8 gap-4 px-4 py-4"
                >
                  {Array.from({ length: 8 }).map((_, i) => (
                    <motion.div
                      key={i}
                      animate={{ opacity: [0.2, 0.4, 0.2] }}
                      transition={{
                        repeat: Infinity,
                        duration: 0.2,
                        delay: i * 0.05,
                      }}
                      className="h-8 bg-gray-100 dark:bg-gray-700 rounded"
                    ></motion.div>
                  ))}
                </motion.div>
              )}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

      {/* Performance indicator */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="px-4 py-2 bg-gray-50 dark:bg-gray-700 text-xs text-gray-500 dark:text-gray-400 text-center"
      >
        High-frequency streaming enabled • {slots.filter((s) => s).length}{" "}
        active flights • ~2 updates/sec
      </motion.div>
    </div>
  );
}
