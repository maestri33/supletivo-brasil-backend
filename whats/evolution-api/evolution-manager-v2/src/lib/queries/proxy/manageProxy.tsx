import { Proxy } from "@/types/evolution.types";

import { api } from "../api";
import { useManageMutation } from "../mutateQuery";

interface IParams {
  instanceName: string;
  token: string;
  data: Proxy;
}

const createProxy = async ({ instanceName, token, data }: IParams) => {
  const response = await api.post(`/proxy/set/${instanceName}`, data, {
    headers: { apikey: token },
  });
  return response.data;
};

export function useManageProxy() {
  const createProxyMutation = useManageMutation(createProxy, {
    invalidateKeys: [["proxy", "fetchProxy"]],
  });

  return {
    createProxy: createProxyMutation,
  };
}
