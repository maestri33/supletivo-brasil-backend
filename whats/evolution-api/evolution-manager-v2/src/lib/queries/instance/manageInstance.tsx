import { NewInstance, Settings } from "@/types/evolution.types";

import { api, apiGlobal } from "../api";
import { useManageMutation } from "../mutateQuery";

const createInstance = async (instance: NewInstance) => {
  const response = await apiGlobal.post("/instance/create", instance);
  return response.data;
};

const restart = async (instanceName: string) => {
  const response = await api.post(`/instance/restart/${instanceName}`);
  return response.data;
};

const logout = async (instanceName: string) => {
  const response = await api.delete(`/instance/logout/${instanceName}`);
  return response.data;
};

const deleteInstance = async (instanceName: string) => {
  const response = await apiGlobal.delete(`/instance/delete/${instanceName}`);
  return response.data;
};

interface ConnectParams {
  instanceName: string;
  token: string;
  number?: string;
}
const connect = async ({ instanceName, token, number }: ConnectParams) => {
  const response = await api.get(`/instance/connect/${instanceName}`, {
    headers: { apikey: token },
    params: { number },
  });
  return response.data;
};

interface UpdateSettingsParams {
  instanceName: string;
  token: string;
  data: Settings;
}
const updateSettings = async ({ instanceName, token, data }: UpdateSettingsParams) => {
  const response = await api.post(`/settings/set/${instanceName}`, data, {
    headers: {
      apikey: token,
    },
  });
  return response.data;
};

export function useManageInstance() {
  const connectMutation = useManageMutation(connect, {
    invalidateKeys: [
      ["instance", "fetchInstance"],
      ["instance", "fetchInstances"],
    ],
  });
  const updateSettingsMutation = useManageMutation(updateSettings, {
    invalidateKeys: [["instance", "fetchSettings"]],
  });
  const deleteInstanceMutation = useManageMutation(deleteInstance, {
    invalidateKeys: [
      ["instance", "fetchInstance"],
      ["instance", "fetchInstances"],
    ],
  });
  const logoutMutation = useManageMutation(logout, {
    invalidateKeys: [
      ["instance", "fetchInstance"],
      ["instance", "fetchInstances"],
    ],
  });
  const restartMutation = useManageMutation(restart, {
    invalidateKeys: [
      ["instance", "fetchInstance"],
      ["instance", "fetchInstances"],
    ],
  });
  const createInstanceMutation = useManageMutation(createInstance, {
    invalidateKeys: [["instance", "fetchInstances"]],
  });

  return {
    connect: connectMutation,
    updateSettings: updateSettingsMutation,
    deleteInstance: deleteInstanceMutation,
    logout: logoutMutation,
    restart: restartMutation,
    createInstance: createInstanceMutation,
  };
}
