import multer, { FileFilterCallback } from "multer";
import fs from "fs";
import path from "path";
import { Request } from "express";
import { AppError } from "../utils/ClassError";

export const allowedExtensions = {
  image: ["image/jpeg", "image/png"],
  video: ["video/mp4"],
  pdf: [
    "application/pdf",
    "application/x-pdf",
    "application/vnd.adobe.pdf"
  ]
};

export const MulterLocal = ({ customExtensions = [] as string[] } = {}) => {

  const storage = multer.diskStorage({

    destination: function (req: Request, file: Express.Multer.File, cb) {

      const userId = req.user?._id;

      if (!userId) {
        return cb(new AppError("User not authenticated", 401), "");
      }

      const fullPath = path.join("uploads", userId.toString());

      if (!fs.existsSync(fullPath)) {
        fs.mkdirSync(fullPath, { recursive: true });
      }

      cb(null, fullPath);
    },

    filename: function (req: Request, file: Express.Multer.File, cb) {

      const uniqueName = `${Date.now()}-${file.originalname}`;
      cb(null, uniqueName);

    }

  });

  const fileFilter = (
    req: Request,
    file: Express.Multer.File,
    cb: FileFilterCallback
  ) => {

    if (customExtensions.length && !customExtensions.includes(file.mimetype)) {
      return cb(new AppError("Invalid file type", 400));
    }

    cb(null, true);
  };

  return multer({ storage, fileFilter });
};