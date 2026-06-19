import axios from "axios";
import type {
  AlertListResponse,
  HCPAwarenessResponse,
  CompetitiveIntelResponse,
  PayerAccessResponse,
} from "../types/actioncenter";

const api = axios.create({ baseURL: "/api/v1" });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("repstream_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export const fetchAlerts = (): Promise<AlertListResponse> =>
  api.get<AlertListResponse>("/action-center/alerts").then((r) => r.data);

export const fetchHCPAwareness = (): Promise<HCPAwarenessResponse> =>
  api.get<HCPAwarenessResponse>("/action-center/hcp-awareness").then((r) => r.data);

export const fetchCompetitiveIntel = (): Promise<CompetitiveIntelResponse> =>
  api.get<CompetitiveIntelResponse>("/action-center/competitive-intel").then((r) => r.data);

export const fetchPayerAccess = (): Promise<PayerAccessResponse> =>
  api.get<PayerAccessResponse>("/action-center/payer-access").then((r) => r.data);
