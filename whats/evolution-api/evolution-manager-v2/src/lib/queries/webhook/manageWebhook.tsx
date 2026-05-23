import { Webhook } from "@/types/evolution.types";

import { api } from "../api";
import { useManageMutation } from "../mutateQuery";

interface IParams {
  instanceName: string;
  token: string;
  data: Webhook;
}

const createWebhook = async ({ instanceName, token, data }: IParams) => {
  const response = await api.post(`/webhook/set/${instanceName}`, { webhook: data }, { headers: { apikey: token } });
  return response.data;
};

export function useManageWebhook() {
  const createWebhookMutation = useManageMutation(createWebhook, {
    invalidateKeys: [["webhook", "fetchWebhook"]],
  });

  return {
    createWebhook: createWebhookMutation,
  };
}
