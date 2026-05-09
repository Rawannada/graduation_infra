import { useCallback } from "react";

const GENERAL_CATEGORY_ID = "69e65b0b17c6dbad8a7757b1";

export function useFiles({ accessToken, setRecentFiles, setGeneralFiles }) {
  const fetchRecent = useCallback(async () => {
    try {
      const res = await fetch("http://localhost:3000/upload/recent", {
        headers: { Authorization: `bearer ${accessToken}` },
      });
      const data = await res.json();
      if (data.files) setRecentFiles(data.files);
    } catch (err) {
      console.error(err);
    }
  }, [accessToken, setRecentFiles]);

  const fetchGeneralFiles = useCallback(async () => {
    try {
      const res = await fetch(
        `http://localhost:3000/upload/files/${GENERAL_CATEGORY_ID}`,
        {
          headers: { Authorization: `bearer ${accessToken}` },
        }
      );
      const data = await res.json();
      if (data.filesWithUrls && setGeneralFiles) {
        setGeneralFiles(data.filesWithUrls);
      }
    } catch (err) {
      console.error(err);
    }
  }, [accessToken, setGeneralFiles]);

  return { fetchRecent, fetchGeneralFiles };
}
