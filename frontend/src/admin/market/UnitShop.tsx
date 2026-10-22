// Staff view of a unit's shop (same screens the entrepreneur uses), to help them set up listings, enter orders and promote.
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../../api";
import ShopManager from "../../components/shop/ShopManager";

export default function UnitShop() {
  const { id } = useParams();
  const [u, setU] = useState<{ id: number; name: string; code: string; owner: { name: string } } | null>(null);
  useEffect(() => {
    api<{ id: number; name: string; code: string; owner: { name: string } }>(`/setup/units/${id}`).then(setU).catch(() => {});
  }, [id]);
  return (
    <div className="stack">
      <Link to={`/admin/setup/units/${id}`} className="small">← Unit</Link>
      <div><h1 style={{ margin: 0 }}>{u?.name ?? "Shop"}</h1><p className="small muted" style={{ margin: 0 }}>{u?.code} · {u?.owner.name} · shop, orders and promotion (M8)</p></div>
      <ShopManager unitId={Number(id)} lang="en" />
    </div>
  );
}
