import { useQuery } from "@tanstack/react-query";

import { api } from "../api";
import { UseQueryParams } from "../types";
import { FetchSettingsResponse } from "./types";

interface IParams {
  instanceName: string | null;
  token: string;
}

const queryKey = (params: Partial<IParams>) => ["instance", "fetchSettings", JSON.stringify(params)];

export const fetchSettings = async ({ instanceName, token }: IParams) => {
  const response = await api.get(`/settings/find/${instanceName}`, {
    headers: { apikey: token },
  });
  return response.data;
};

export const useFetchSettings = (props: UseQueryParams<FetchSettingsResponse> & Partial<IParams>) => {
  const { instanceName, token, ...rest } = props;
  return useQuery<FetchSettingsResponse>({
    ...rest,
    queryKey: queryKey({ instanceName, token }),
    queryFn: () => fetchSettings({ instanceName: instanceName!, token: token! }),
    enabled: !!instanceName,
  });
};
