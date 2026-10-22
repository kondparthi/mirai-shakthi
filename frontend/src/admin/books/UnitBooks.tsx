// Staff view of a unit's books (the same screens the entrepreneur uses), to help with entries and check the business.
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../../api";
import BooksManager from "../../components/books/BooksManager";

export default function UnitBooks() {
  const { id } = useParams();
  const [u, setU] = useState<{ id: number; name: string; code: string; owner: { name: string } } | null>(null);
  useEffect(() => {
    api<{ id: number; name: string; code: string; owner: { name: string } }>(`/setup/units/${id}`).then(setU).catch(() => {});
  }, [id]);
  return (
    <div className="stack">
      <Link to={`/admin/setup/units/${id}`} className="small">← Unit</Link>
      <div><h1 style={{ margin: 0 }}>{u?.name ?? "Accounts"}</h1><p className="small muted" style={{ margin: 0 }}>{u?.code} · {u?.owner.name} · daily accounts, stock, EMIs and monthly summaries (M9)</p></div>
      <BooksManager unitId={Number(id)} lang="en" staffView />
    </div>
  );
}
