import { useQuery } from "@tanstack/react-query";

import { api } from "../api";
import { UseQueryParams } from "../types";
import { FetchWebhookResponse } from "./types";

interface IParams {
  instanceName: string | null;
  token: string;
}

const queryKey = (params: Partial<IParams>) => ["webhook", "fetchWebhook", JSON.stringify(params)];

export const fetchWebhook = async ({ instanceName, token }: IParams) => {
  const response = await api.get(`/webhook/find/${instanceName}`, {
    headers: { apiKey: token },
  });
  return response.data;
};

export const useFetchWebhook = (props: UseQueryParams<FetchWebhookResponse> & Partial<IParams>) => {
  const { instanceName, token, ...rest } = props;
  return useQuery<FetchWebhookResponse>({
    ...rest,
    queryKey: queryKey({ instanceName, token }),
    queryFn: () => fetchWebhook({ instanceName: instanceName!, token: token! }),
    enabled: !!instanceName,
  });
};
