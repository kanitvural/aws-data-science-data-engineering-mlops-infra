
// types/flight.ts
export interface FlightData {
  id: string;
  year: number;
  month: number;
  day: number;
  dep_time: string;
  sched_dep_time: string;
  arr_time: string;
  sched_arr_time: string;
  arr_delay: number;
  carrier: string;
  flight: number;
  tailnum: string;
  origin: string;
  dest: string;
  air_time: number;
  distance: number;
  hour: number;
  minute: number;
  airline: string;
  route: string;
  temp: number;
  dewp: number;
  humid: number;
  wind_dir: number;
  wind_speed: number;
  wind_gust: number;
  precip: number;
  pressure: number;
  visib: number;
  date: string;
  date_string: string;
  dep_delay: number | null;
  timestamp: string;
}

export interface FlightTableData extends Omit<FlightData, 'year' | 'month' | 'day' | 'visib' | 'date' | 'date_string'> {}

// Yeni grid slot interface
export interface FlightSlot {
  id: string;
  flight: FlightTableData | null;
  status: 'empty' | 'new' | 'waiting' | 'predicted' | 'exiting';
  position: number; // 0-11 arası sabit pozisyon
}
