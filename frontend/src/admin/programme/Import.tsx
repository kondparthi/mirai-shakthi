import { useState } from "react";
import { apiDownload } from "../../api";
import CsvImport from "../CsvImport";

export default function Import() {
  const [source, setSource] = useState("import");
  return (
    <div className="stack" style={{ maxWidth: 1100 }}>
      <div><h1>Bulk import entrepreneurs</h1>
        <p className="muted small" style={{ margin: 0 }}>For lists from SHG federations, partners and campaigns. Aadhaar and bank details are not imported – they are added later, in person.
          Imported people give their own consent the first time they open the app with their mobile number.</p></div>
      <div className="card stack">
        <div className="row-gap" style={{ alignItems: "flex-end" }}>
          <button className="btn secondary" onClick={() => apiDownload("/programme/import/template", "entrepreneurs_template.csv")}>Download template</button>
          <label className="field"><span>Where the list came from</span>
            <select className="input" value={source} onChange={(e) => setSource(e.target.value)}>
              <option value="import">Bulk import</option><option value="partner">Partner</option><option value="campaign">Campaign</option>
            </select></label>
        </div>
        <ul className="small muted" style={{ margin: 0 }}>
          <li>Use the <b>codes</b> from Master data (e.g. district <code>guntur</code>, skill <code>cooking</code>, sector <code>food</code>). Separate several skills with <code>;</code></li>
          <li>Dates as YYYY-MM-DD or DD-MM-YYYY. Age must be 18–60. Save the file as CSV (UTF-8) from Excel.</li>
          <li>Nothing is saved until you press Import; rows with problems must be fixed first.</li>
        </ul>
        <CsvImport key={source} path={`/programme/import?source=${source}`}
          columns={[["mobile", "Mobile"], ["full_name", "Name"], ["gender", "Gender"], ["dob", "DOB"], ["district", "District"], ["mandal", "Mandal"],
            ["village", "Village"], ["skills", "Skills"], ["interests", "Interests"]]} />
      </div>
    </div>
  );
}
