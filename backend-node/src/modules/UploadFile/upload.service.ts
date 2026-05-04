import { NextFunction, Request, Response } from "express";
import { AppError } from "../../utils/ClassError";
import { FileRepository } from "../../DB/repositories/file.repository";
import fileModel, { IFile } from "../../DB/models/File.model";
import { CategoryRepository } from "../../DB/repositories/category.repository";
import categoryModel from "../../DB/models/category.model";
import axios from "axios";
import { unlink } from "fs/promises";
class UploadService {
  private aiBaseUrlCsv: string;
  private aiBaseUrlPdf: string;

  constructor() {
    this.aiBaseUrlCsv = process.env.AI_CSV_URL || "http://localhost:5001";
    this.aiBaseUrlPdf = process.env.AI_PDF_URL || "http://localhost:8000";
  }
  private _fileModel = new FileRepository(fileModel);
  private _categoryModel = new CategoryRepository(categoryModel);


  upload = async (req: Request, res: Response, next: NextFunction) => {
    const file = (req as any).file as Express.Multer.File | undefined;
    const userId = req?.user?._id;

    if (!file || !file.path || !userId)
      throw new AppError("Upload failed, Missing the file or UserId", 404);

    const generalCategory = await this._categoryModel.findOne({
      userId,
      categoryName: "General Category",
    });

    if (!generalCategory) throw new AppError("Category Not Found", 404);

    const pdf = await this._fileModel.create({
      userId,
      categoryId: generalCategory?._id!,
      fileName: req?.file?.filename!,
      path: req?.file?.path!,
      fileType: "pdf",
    });

    return res.status(200).json({ message: "File uploaded successfully", pdf });
  };

  recentFiles = async (req: Request, res: Response, next: NextFunction) => {
    const userId = req?.user?._id;

    if (!userId) {
      throw new AppError("User Not Found", 404);
    }

    const files = await this._fileModel.find({ filter: { userId } });

    const filesWithUrls = files.map((file) => {
      return {
        ...file.toObject(),
        fileName: file.fileName.replace(/^\d+-/, ""),
        url: `${req.protocol}://${req.get("host")}/${file.path.replace(/\\/g, "/")}`,
      };
    });

    if (filesWithUrls.length == 0)
      return res.status(200).json({ message: "No Files Uploaded Yet" });

    return res.status(200).json({
      message: "success",
      files: filesWithUrls,
    });
  };

  deleteFile = async (req: Request, res: Response, next: NextFunction) => {
    const { fileId } = req.params;

    const file = await this._fileModel.findOne({ _id: fileId });

    if (!file) throw new AppError("File not found", 404);

    if (req?.user?._id.toString() !== file.userId.toString())
      throw new AppError("You are not authorized", 401);

    await unlink(file.path);
    await this._fileModel.findOneAndDelete({ _id: fileId });

    return res.status(200).json({ message: "File deleted" });
  };

  searchFiles = async (req: Request, res: Response, next: NextFunction) => {
    const userId = req.user?._id;
    const search =
      typeof req.query.search === "string" ? req.query.search.trim() : "";

    if (!userId) {
      throw new AppError("User not found", 404);
    }

    const files = await this._fileModel.find({
      filter: { userId, fileName: { $regex: search, $options: "i" } },
    });

    if (files.length === 0) {
      return res.status(200).json({ message: "No matched file", files: [] });
    }

    const filesWithUrls = files.map((file) => ({
      ...file.toObject(),
      fileName: file.fileName.replace(/^\d+-/, ""),
      url: `${req.protocol}://${req.get("host")}/${file.path.replace(/\\/g, "/")}`,
    }));

    return res.status(200).json({
      message: "success",
      files: filesWithUrls,
    });
  };

  addToCategory = async (req: Request, res: Response, next: NextFunction) => {
    const { useGeneral, newCategoryName, categoryId } = req.body;
    const { fileId } = req.params;
    const userId = req.user?._id;

    if (!fileId) throw new AppError("File Not Found", 404);
    if (!userId) throw new AppError("User Not Found", 404);

    const file = await this._fileModel.findOne({ _id: fileId, userId });
    if (!file) throw new AppError("File not found or unauthorized", 404);

    const optionsCount = [useGeneral, categoryId, newCategoryName].filter(
      Boolean,
    ).length;

    if (optionsCount !== 1) {
      throw new AppError("Choose only one option", 400);
    }

    let finalCategoryId;

    if (useGeneral) {
      const general = await this._categoryModel.findOne({
        userId,
        categoryName: "General Category",
      });

      if (!general) {
        throw new AppError("General category not found", 500);
      }

      finalCategoryId = general._id;
    } else if (categoryId) {
      const category = await this._categoryModel.findOne({
        _id: categoryId,
        userId,
      });

      if (!category) {
        throw new AppError("Invalid category", 400);
      }

      finalCategoryId = category._id;
    } else if (newCategoryName) {
      const name = newCategoryName.trim().toLowerCase();

      if (!name) {
        throw new AppError("Invalid category name", 400);
      }

      let category = await this._categoryModel.findOne({
        categoryName: name,
        userId,
      });

      if (!category) {
        category = await this._categoryModel.create({
          categoryName: name,
          userId,
        });
      }

      finalCategoryId = category._id;
    }

    await this._fileModel.findOneAndUpdate(
      { _id: fileId, userId },
      { categoryId: finalCategoryId },
      { new: true },
    );

    return res.status(200).json({ message: "Success" });
  };

  // getAllCategories = async (
  //   req: Request,
  //   res: Response,
  //   next: NextFunction,
  // ) => {
  //   const userId = req?.user?._id;

  //   if (!userId) throw new AppError("User not found", 404);

  //   const categories = await this._categoryModel.find({ filter: { userId } });

  //   if (!categories)
  //     return res.status(200).json({ message: "No categories for this user" });

  //   return res.status(200).json({ message: "success", categories });
  // };

  getAllCategories = async (
    req: Request,
    res: Response,
    next: NextFunction,
  ) => {
    const userId = req?.user?._id;

    if (!userId) throw new AppError("User not found", 404);

    const categories = await this._categoryModel.find({ filter: { userId } });

    if (!categories.length) {
      return res.status(200).json({ message: "No categories for this user" });
    }

    const updatedCategories = categories.map((category) => {
      const words = category.categoryName.trim().split(" ");

      const code = words
        .slice(0, 2)
        .map((word) => word[0])
        .join("")
        .toUpperCase();

      return {
        ...category.toObject(),
        code,
      };
    });

    return res.status(200).json({
      message: "success",
      categories: updatedCategories,
    });
  };

  deleteCategory = async (req: Request, res: Response, next: NextFunction) => {
    const { categoryId } = req.params;
    const userId = req?.user?._id;

    if (!userId) throw new AppError("User Not Found", 404);

    const category = await this._categoryModel.findOne({
      _id: categoryId,
      userId,
    });

    if (!category)
      throw new AppError("Category Not Found Or not authorized", 401);

    if (category.categoryName == "General Category")
      throw new AppError("General Category cannot be deleted", 403);

    const general = await this._categoryModel.findOne({
      categoryName: "General Category",
      userId,
    });
    if (!general) throw new AppError("General category Not found", 404);

    await this._fileModel.updateMany(
      { categoryId: category._id },
      { categoryId: general._id },
    );
    await this._categoryModel.findOneAndDelete({ _id: categoryId });

    return res.status(200).json({ message: "Category deleted successfully" });
  };

  addCategory = async (req: Request, res: Response, next: NextFunction) => {
    const { categoryName } = req.body;
    const userId = req?.user?._id;

    if (!userId) throw new AppError("User Not Found", 404);

    const category = await this._categoryModel.findOne({ categoryName });
    if (category)
      return res
        .status(200)
        .json({ message: "Category with this name already exists" });

    const newCategory = await this._categoryModel.create({
      categoryName,
      userId,
    });

    return res.status(201).json({ message: "Created", newCategory });
  };

  getFilesInCategory = async (
    req: Request,
    res: Response,
    next: NextFunction,
  ) => {
    const { categoryId } = req.params;
    const userId = req?.user?._id;

    if (!userId) throw new AppError("User Not Found", 404);

    if (!categoryId) throw new AppError("CategoryId incorrect", 404);

    const category = await this._categoryModel.findOne({ _id: categoryId });
    if (!category) throw new AppError("Category Not Found", 404);

    if (category.userId.toString() !== userId.toString())
      throw new AppError("You are not authorized", 401);

    const files = await this._fileModel.find({
      filter: {
        userId,
        categoryId,
      },
    });

    const filesWithUrls = files.map((file) => ({
      ...file.toObject(),
      fileName: file.fileName.replace(/^\d+-/, ""),
      url: `${req.protocol}://${req.get("host")}/${file.path.replace(/\\/g, "/")}`,
    }));

    return res.status(200).json({ message: "success", filesWithUrls });
  };

  addFile = async (req: Request, res: Response, next: NextFunction) => {
    const { categoryId } = req.params;
    const userId = req?.user?._id;
    const file = req?.file;

    if (!userId) throw new AppError("User not found", 404);

    if (!categoryId) throw new AppError("CategoryId not correct", 404);
    if (!file) throw new AppError("No file uploaded", 400);

    const category = await this._categoryModel.findOne({
      _id: categoryId,
      userId,
    });

    if (!category) throw new AppError("Category not found", 404);

    const newFile = await this._fileModel.create({
      userId,
      categoryId: category?._id!,
      fileName: file.filename,
      path: file.path,
      fileType: "pdf",
    });

    const cleanFileName = newFile.fileName.replace(/^\d+-/, "");

    return res.status(201).json({
      message: "file added successfully",
      file: {
        ...newFile.toObject(),
        fileName: cleanFileName,
      },
      url: `${req.protocol}://${req.get("host")}/uploads/${file.filename}`,
    });
  };

  uploadCSVFile = async (req: Request, res: Response, next: NextFunction) => {
    const file = (req as any).file as Express.Multer.File | undefined;
    const userId = req?.user?._id;

    if (!file || !file.path || !userId)
      throw new AppError("Upload failed, Missing file or userId", 400);

    const generalCategory = await this._categoryModel.findOne({
      userId,
      categoryName: "General Category",
    });

    if (!generalCategory) throw new AppError("Category Not Found", 404);

    const CSV = await this._fileModel.create({
      userId,
      categoryId: generalCategory._id,
      fileName: file.filename,
      path: file.path,
      fileType: "csv",
    });

    const aiResponse = await axios.post(
      `${this.aiBaseUrlCsv}/upload`,
      {
        CSV: {
          _id: CSV._id.toString(),
          userId: CSV.userId.toString(),
          categoryId: CSV.categoryId.toString(),
          fileName: CSV.fileName,
          path: CSV.path,
          fileType: CSV.fileType,
        },
      },
      {
        timeout: 600000,
      },
    );

    const autoclean = aiResponse.data.autoclean;
    // const autoclean : IFile["autoclean"]= {
    //     status: "success",
    //     raw_shape: [1000, 12],
    //     clean_shape: [950, 12],
    //     rows_removed: 50,
    //     cleaned_path: "..._autoclean.parquet",
    //     ready_for_charts: true,
    // };

    CSV.autoclean = autoclean;
    await CSV.save();

    const cleanFileName = CSV.fileName.replace(/^\d+-/, "");
    return res.status(200).json({
      message: "File uploaded successfully",
      CSV: {
        ...CSV.toObject(),
        fileName: cleanFileName,
      },
      autoclean,
    });
  };
}

export default new UploadService();