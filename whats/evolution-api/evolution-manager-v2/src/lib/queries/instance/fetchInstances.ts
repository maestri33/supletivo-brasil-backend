import { useQuery } from "@tanstack/react-query";

import { apiGlobal } from "../api";
import { UseQueryParams } from "../types";
import { FetchInstancesResponse } from "./types";

const queryKey = ["instance", "fetchInstances"];

export const fetchInstances = async () => {
  const response = await apiGlobal.get(`/instance/fetchInstances`);
  return response.data;
};

export const useFetchInstances = (props?: UseQueryParams<FetchInstancesResponse>) => {
  return useQuery<FetchInstancesResponse>({
    ...props,
    queryKey,
    queryFn: () => fetchInstances(),
  });
};
