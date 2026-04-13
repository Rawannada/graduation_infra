import { Router } from "express";
import { Authentication } from "../../middleware/Authentication";
import { allowedExtensions, MulterLocal } from "../../middleware/Multer";
import { validation } from "../../middleware/validation";
import * as UPV from "./upload.validation";
import UPS from "./upload.service";

const uploadRouter = Router();

uploadRouter.post(
    "/",
    Authentication(),
    MulterLocal({ customExtensions: allowedExtensions.pdf }).single("file"),
    UPS.upload,
);
uploadRouter.get("/recent", Authentication(), UPS.recentFiles);
uploadRouter.post(
    "/addFile/:categoryId",
    Authentication(),
    MulterLocal({ customExtensions: allowedExtensions.pdf }).single("file"),
    UPS.addFile,
);
uploadRouter.delete("/delete/:fileId", Authentication(), UPS.deleteFile);
uploadRouter.get("/search", Authentication(), UPS.searchFiles);
uploadRouter.post("/add", Authentication(), UPS.addCategory);
uploadRouter.post("/addCategory/:fileId", Authentication(), UPS.addToCategory);
uploadRouter.get("/categories", Authentication(), UPS.getAllCategories);
uploadRouter.get(
    "/files/:categoryId",
    Authentication(),
    UPS.getFilesInCategory,
);
uploadRouter.delete(
    "/category/:categoryId",
    Authentication(),
    UPS.deleteCategory,
);

export default uploadRouter;