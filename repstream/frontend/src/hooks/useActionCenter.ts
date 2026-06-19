import { useQuery } from "@tanstack/react-query";
import {
  fetchAlerts,
  fetchHCPAwareness,
  fetchCompetitiveIntel,
  fetchPayerAccess,
} from "../api/actionCenter";

export const useAlerts = () =>
  useQuery({ queryKey: ["action-center", "alerts"], queryFn: fetchAlerts, staleTime: 5 * 60 * 1000 });

export const useHCPAwareness = () =>
  useQuery({ queryKey: ["action-center", "hcp-awareness"], queryFn: fetchHCPAwareness, staleTime: 5 * 60 * 1000 });

export const useCompetitiveIntel = () =>
  useQuery({ queryKey: ["action-center", "competitive-intel"], queryFn: fetchCompetitiveIntel, staleTime: 5 * 60 * 1000 });

export const usePayerAccess = () =>
  useQuery({ queryKey: ["action-center", "payer-access"], queryFn: fetchPayerAccess, staleTime: 5 * 60 * 1000 });
