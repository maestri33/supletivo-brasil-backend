import { useQuery } from "@tanstack/react-query";

import { api } from "../api";
import { UseQueryParams } from "../types";
import { FetchProxyResponse } from "./types";

interface IParams {
  instanceName: string | null;
  token: string;
}

const queryKey = (params: Partial<IParams>) => ["proxy", "fetchProxy", JSON.stringify(params)];

export const fetchProxy = async ({ instanceName, token }: IParams) => {
  const response = await api.get(`/proxy/find/${instanceName}`, {
    headers: { apiKey: token },
  });
  return response.data;
};

export const useFetchProxy = (props: UseQueryParams<FetchProxyResponse> & Partial<IParams>) => {
  const { instanceName, token, ...rest } = props;
  return useQuery<FetchProxyResponse>({
    ...rest,
    queryKey: queryKey({ instanceName, token }),
    queryFn: () => fetchProxy({ instanceName: instanceName!, token: token! }),
    enabled: !!instanceName,
  });
};
