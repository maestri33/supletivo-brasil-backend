import { ChevronsUpDown, CircleUser, Cog, MessageCircle, RefreshCw } from "lucide-react";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { toast } from "react-toastify";

import { InstanceStatus } from "@/components/instance-status";
import { InstanceToken } from "@/components/instance-token";
import { Avatar, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader } from "@/components/ui/card";
import { Dialog, DialogClose, DialogContent, DialogFooter, DialogHeader } from "@/components/ui/dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuCheckboxItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";

import { useFetchInstances } from "@/lib/queries/instance/fetchInstances";
import { useManageInstance } from "@/lib/queries/instance/manageInstance";

import { Instance } from "@/types/evolution.types";

import { NewInstance } from "./NewInstance";
import { TooltipWrapper } from "@/components/ui/tooltip";

function Dashboard() {
  const { t } = useTranslation();

  const [deleteConfirmation, setDeleteConfirmation] = useState<string | null>(null);
  const { deleteInstance, logout } = useManageInstance();
  const { data: instances, refetch } = useFetchInstances();
  const [deleting, setDeleting] = useState<string[]>([]);
  const [searchStatus, setSearchStatus] = useState("all");
  const [nameSearch, setNameSearch] = useState("");

  const resetTable = async () => {
    await refetch();
  };

  const handleDelete = async (instanceName: string) => {
    setDeleteConfirmation(null);
    setDeleting([...deleting, instanceName]);
    try {
      try {
        await logout(instanceName);
      } catch (error) {
        console.error("Error logout:", error);
      }
      await deleteInstance(instanceName);
      await new Promise((resolve) => setTimeout(resolve, 1000));
      resetTable();
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } catch (error: any) {
      console.error("Error instance delete:", error);
      toast.error(`Error : ${error?.response?.data?.response?.message}`);
    } finally {
      setDeleting(deleting.filter((item) => item !== instanceName));
    }
  };

  const filteredInstances = useMemo(() => {
    let instancesList = instances ? [...instances] : [];
    if (searchStatus !== "all") {
      instancesList = instancesList.filter((instance) => instance.connectionStatus === searchStatus);
    }

    if (nameSearch !== "") {
      instancesList = instancesList.filter((instance) => instance.name.toLowerCase().includes(nameSearch.toLowerCase()));
    }

    return instancesList;
  }, [instances, nameSearch, searchStatus]);

  const instanceStatus = [
    { value: "all", label: t("status.all") },
    { value: "close", label: t("status.closed") },
    { value: "connecting", label: t("status.connecting") },
    { value: "open", label: t("status.open") },
  ];

  return (
    <div className="my-4 px-4">
      <div className="flex w-full items-center justify-between">
        <h2 className="text-lg">{t("dashboard.title")}</h2>
        <div className="flex gap-2">
          <Button variant="outline" size="icon">
            <RefreshCw onClick={resetTable} size="20" />
          </Button>
          <NewInstance resetTable={resetTable} />
        </div>
      </div>
      <div className="my-4 flex items-center justify-between gap-3 px-4">
        <div className="flex-1">
          <Input placeholder={t("dashboard.search")} value={nameSearch} onChange={(e) => setNameSearch(e.target.value)} />
        </div>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="secondary">
              {t("dashboard.status")} <ChevronsUpDown size="15" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent>
            {instanceStatus.map((status) => (
              <DropdownMenuCheckboxItem
                key={status.value}
                checked={searchStatus === status.value}
                onCheckedChange={(checked) => {
                  if (checked) {
                    setSearchStatus(status.value);
                  }
                }}>
                {status.label}
              </DropdownMenuCheckboxItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      <main className="grid gap-6 sm:grid-cols-2 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {filteredInstances.length > 0 &&
          Array.isArray(filteredInstances) ? (
          filteredInstances.map((instance: Instance) => (
            <Card key={instance.id}>
              <CardHeader>
                <Link to={`/manager/instance/${instance.id}/dashboard`} className="flex w-full flex-row items-center justify-between gap-4">
                  <TooltipWrapper content={instance.name} side="top">
                    <h3 className="text-wrap font-semibold truncate">{instance.name}</h3>
                  </TooltipWrapper>

                  <TooltipWrapper content={t("dashboard.settings")} side="top">
                    <Button variant="ghost" size="icon">
                      <Cog className="card-icon" size="20" />
                    </Button>
                  </TooltipWrapper>
                </Link>
              </CardHeader>
              <CardContent className="flex-1 space-y-6">
                <InstanceToken token={instance.token} />
                <div className="flex w-full flex-wrap">
                  <div className="flex flex-1 gap-2">
                    {instance.profileName && (
                      <>
                        <Avatar>
                          <AvatarImage src={instance.profilePicUrl} alt="" />
                        </Avatar>
                        <div className="space-y-1">
                          <strong>{instance.profileName}</strong>
                          <p className="text-sm text-muted-foreground">{instance.ownerJid && instance.ownerJid.split("@")[0]}</p>
                        </div>
                      </>
                    )}
                  </div>

                  <div className="flex items-center justify-end gap-4 text-sm">
                    <div className="flex flex-col items-center justify-center gap-1">
                      <CircleUser className="text-muted-foreground" size="20" />
                      <span>{new Intl.NumberFormat("pt-BR").format(instance?._count?.Contact || 0)}</span>
                    </div>
                    <div className="flex flex-col items-center justify-center gap-1">
                      <MessageCircle className="text-muted-foreground" size="20" />
                      <span>{new Intl.NumberFormat("pt-BR").format(instance?._count?.Message || 0)}</span>
                    </div>
                  </div>
                </div>
              </CardContent>
              <CardFooter className="justify-between">
                <InstanceStatus status={instance.connectionStatus} />
                <Button variant="destructive" size="sm" onClick={() => setDeleteConfirmation(instance.name)} disabled={deleting.includes(instance.name)}>
                  {deleting.includes(instance.name) ? <span>{t("button.deleting")}</span> : <span>{t("button.delete")}</span>}
                </Button>
              </CardFooter>
            </Card>
          ))) :(
          <p>{t("dashboard.instancesNotFound")}</p>
          )}
      </main>

      {!!deleteConfirmation && (
        <Dialog onOpenChange={() => setDeleteConfirmation(null)} open>
          <DialogContent>
            <DialogClose />
            <DialogHeader>{t("modal.delete.title")}</DialogHeader>
            <p>{t("modal.delete.message", { instanceName: deleteConfirmation })}</p>
            <DialogFooter>
              <div className="flex items-center gap-4">
                <Button onClick={() => setDeleteConfirmation(null)} size="sm" variant="outline">
                  {t("button.cancel")}
                </Button>
                <Button onClick={() => handleDelete(deleteConfirmation)} variant="destructive">
                  {t("button.delete")}
                </Button>
              </div>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}

export default Dashboard;
