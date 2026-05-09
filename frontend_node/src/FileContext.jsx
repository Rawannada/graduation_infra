import {
  createContext,
  useState,
  useCallback,
  useEffect,
  useContext,
} from "react";

import { AuthContext } from "./AuthContext";
export const FileContext = createContext();

export function FileProvider({ children }) {
  const [pdfFiles, setPdfFiles] = useState([]);
  const [csvFiles, setCsvFiles] = useState([]);
  const [recentFiles, setRecentFiles] = useState([]);
  const [generalFiles, setGeneralFiles] = useState([]);
  const [categories, setCategories] = useState([]);
  const [categoryFiles, setCategoryFiles] = useState({});
  const [generalCategoryId, setGeneralCategoryId] = useState(null);
  // ── Network fetches ──────────────────────────────────────────────────────
  const { token } = useContext(AuthContext);
  const fetchRecentFiles = useCallback(async (token) => {
    try {
      const res = await fetch("/api/upload/recent", {
        headers: { Authorization: `bearer ${token}` },
      });
      const data = await res.json();
      setRecentFiles(data.files || []);
    } catch (err) {
      console.error(err);
    }
  }, []);

  const fetchGeneralFiles = useCallback(async (token, categoryId) => {
    if (!categoryId) return;

    try {
      const res = await fetch(
        `/api/upload/files/${categoryId}`,
        { headers: { Authorization: `bearer ${token}` } },
      );

      const data = await res.json();

      if (data.filesWithUrls) {
        setGeneralFiles(data.filesWithUrls);
      }
    } catch (err) {
      console.error(err);
    }
  }, []);

  const fetchCategories = useCallback(async (token) => {
    try {
      const res = await fetch("/api/upload/categories", {
        headers: { Authorization: `bearer ${token}` },
      });

      const data = await res.json();
      console.log("Fetched categories:", data.categories);
      const categories = data.categories || [];
      setCategories(categories);

      const general = categories.find(
        (c) => c.categoryName === "General Category",
      );

      setGeneralCategoryId(general?._id || null);
    } catch (err) {
      console.error(err);
    }
  }, []);

  const fetchCategoryFiles = useCallback(async (token, categoryId) => {
    try {
      const res = await fetch(
        `/api/upload/files/${categoryId}`,
        { headers: { Authorization: `bearer ${token}` } },
      );
      const data = await res.json();
      const files = data.filesWithUrls || data.files || [];
      setCategoryFiles((prev) => ({ ...prev, [categoryId]: files }));
    } catch (err) {
      console.error(err);
    }
  }, []);

  // ── Optimistic helpers ───────────────────────────────────────────────────

  /** After any upload → add to recentFiles + generalFiles + general bucket instantly */
  const optimisticAddFile = useCallback((file) => {
    setRecentFiles((prev) =>
      prev.find((f) => f._id === file._id) ? prev : [file, ...prev],
    );
    setGeneralFiles((prev) =>
      prev.find((f) => f._id === file._id) ? prev : [file, ...prev],
    );
    setCategoryFiles((prev) => {
      const existing = prev[generalCategoryId] || [];
      if (existing.find((f) => f._id === file._id)) return prev;
      return { ...prev, [generalCategoryId]: [file, ...existing] };
    });
  }, []);

  /** Move file from general → existing category */
  const optimisticMoveToCategory = useCallback((file, targetCategoryId) => {
    setGeneralFiles((prev) => prev.filter((f) => f._id !== file._id));
    setCategoryFiles((prev) => {
      const genFiles = (prev[generalCategoryId] || []).filter(
        (f) => f._id !== file._id,
      );
      const catFiles = prev[targetCategoryId] || [];
      return {
        ...prev,
        [generalCategoryId]: genFiles,
        [targetCategoryId]: catFiles.find((f) => f._id === file._id)
          ? catFiles
          : [file, ...catFiles],
      };
    });
  }, []);

  /** Create new category + move file into it from general */
  const optimisticAddCategoryWithFile = useCallback((newCategory, file) => {
    setCategories((prev) =>
      prev.find((c) => c._id === newCategory._id)
        ? prev
        : [...prev, newCategory],
    );
    setGeneralFiles((prev) => prev.filter((f) => f._id !== file._id));
    setCategoryFiles((prev) => {
      const genFiles = (prev[generalCategoryId] || []).filter(
        (f) => f._id !== file._id,
      );
      return {
        ...prev,
        [generalCategoryId]: genFiles,
        [newCategory._id]: [file],
      };
    });
  }, []);

  /** Add a file directly into a category bucket (CategoryFiles page / Sidebar upload) */
  const optimisticAddFileToCategory = useCallback((categoryId, file) => {
    setCategoryFiles((prev) => {
      const existing = prev[categoryId] || [];
      if (existing.find((f) => f._id === file._id)) return prev;
      return { ...prev, [categoryId]: [file, ...existing] };
    });
    setRecentFiles((prev) =>
      prev.find((f) => f._id === file._id) ? prev : [file, ...prev],
    );
  }, []);

  /** Remove a category from the list */
  const optimisticRemoveCategory = useCallback((categoryId) => {
    setCategories((prev) => prev.filter((c) => c._id !== categoryId));
    setCategoryFiles((prev) => {
      const next = { ...prev };
      delete next[categoryId];
      return next;
    });
  }, []);

  /**
   * Remove a file everywhere instantly:
   * recentFiles, generalFiles, AND every category bucket that contains it.
   * Called from Sidebar delete.
   */
  const optimisticRemoveFile = useCallback((fileId) => {
    setRecentFiles((prev) => prev.filter((f) => f._id !== fileId));
    setGeneralFiles((prev) => prev.filter((f) => f._id !== fileId));
    setCategoryFiles((prev) => {
      const next = {};
      for (const [catId, files] of Object.entries(prev)) {
        next[catId] = files.filter((f) => f._id !== fileId);
      }
      return next;
    });
  }, []);
  useEffect(() => {
    if (generalCategoryId && token) {
      fetchGeneralFiles(token, generalCategoryId);
    }
  }, [generalCategoryId, token, fetchGeneralFiles]);
  return (
    <FileContext.Provider
      value={{
        // original
        pdfFiles,
        setPdfFiles,
        csvFiles,
        setCsvFiles,
        recentFiles,
        setRecentFiles,
        generalFiles,
        setGeneralFiles,
        fetchRecentFiles,
        fetchGeneralFiles,
        // new shared state
        categories,
        setCategories,
        categoryFiles,
        setCategoryFiles,
        fetchCategories,
        fetchCategoryFiles,
        // optimistic helpers
        optimisticAddFile,
        optimisticMoveToCategory,
        optimisticAddCategoryWithFile,
        optimisticAddFileToCategory,
        optimisticRemoveCategory,
        optimisticRemoveFile, // ← NEW
      }}
    >
      {children}
    </FileContext.Provider>
  );
}
