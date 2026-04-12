import{ CirclePlus} from "lucide-react";
import { useState } from "react";
export default function AddCategoryModal({ onClose, onSave }) {
   const [title, setTitle] = useState("");
  const [desc, setDesc] = useState("");
const accessToken = localStorage.getItem("accessToken");
  async function handleSave() {
  if (!title.trim()) return;

  try {
    const res = await fetch("http://localhost:3000/upload/add", {
      method: "POST",
      headers: {
        Authorization: `bearer ${accessToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        categoryName: title,
      }),
    });

    const data = await res.json();

    if (!res.ok) {
      alert(data.message); // زي: name already exists
      return;
    }

    console.log("Category added:", data);

    onSave(data); // نرجع الداتا الحقيقية
    onClose();
  } catch (err) {
    console.error(err);
  }
}

  return (
    <div style={styles.overlay}>
      <div style={styles.modal}>
        
        <div style={styles.header}>
          <h2>Add Category</h2>
          <button className="close-modal" onClick={onClose}>
            <CirclePlus size={28} />
          </button>
        </div>

        <div style={styles.body}>
          <label>Title</label>
          <input style={styles.input} type="text" placeholder="Cat Name" value={title}
  onChange={(e) => setTitle(e.target.value)} />

          <label>Description</label>
          <input style={styles.input} type="text" placeholder="Put your description" value={desc}
  onChange={(e) => setDesc(e.target.value)} />
        </div>

        <div style={styles.footer}>
          <button style={styles.cancel} onClick={onClose}>
            Cancel
          </button>
          <button style={styles.save} onClick={handleSave}>
            Save
          </button>
        </div>

      </div>
    </div>
  );
}
const styles = {
  overlay: {
    position: "fixed",
    top: 0,
    left: 0,
    width: "100%",
    height: "100%",
    background: "rgba(0,0,0,0.4)",
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
  },
  modal: {
    background: "#fff",
    padding: "16px 23px",
    borderRadius: "16px",
    width: "484px",
    height: "320px",
    // background:"tomato"
  },
  header: {
   height: "56px",
    // background:"tomato",
    color:"#113567",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  body: {
    display: "flex",
    flexDirection: "column",
    gap: "10px",
    marginTop: "15px",
  },
  input: {
    height: "40px",
    padding: "8px",
    borderRadius: "16px",
    border: "1px solid #ccc",
  },
  footer: {
    display: "flex",
    justifyContent: "space-between",
    marginTop: "20px",
  },
  cancel: {
    color: "red",
    background: "none",
    border: "none",
    cursor: "pointer",
  },
  save: {
   
    color: "#113567",
    border: "none",
    padding: "8px 16px",
    borderRadius: "16px",
    cursor: "pointer",
    background:"transparent",
    
  },
};