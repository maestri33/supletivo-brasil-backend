import { useQuery } from "@tanstack/react-query";

import { apiGlobal } from "../api";
import { UseQueryParams } from "../types";
import { FetchInstanceResponse } from "./types";

interface IParams {
  instanceId: string | null;
}

const queryKey = (params: Partial<IParams>) => ["instance", "fetchInstance", JSON.stringify(params)];

export const fetchInstance = async ({ instanceId }: IParams) => {
  const response = await apiGlobal.get(`/instance/fetchInstances`, {
    params: { instanceId },
  });
  if (Array.isArray(response.data)) {
    return response.data[0];
  }
  return response.data;
};

export const useFetchInstance = (props: UseQueryParams<FetchInstanceResponse> & Partial<IParams>) => {
  const { instanceId, ...rest } = props;
  return useQuery<FetchInstanceResponse>({
    ...rest,
    queryKey: queryKey({ instanceId }),
    queryFn: () => fetchInstance({ instanceId: instanceId! }),
    enabled: !!instanceId,
  });
};
