import express, { Router, Request, Response } from "express";
import { db } from "./db";

const router = Router();

/**
 * User Routes
 */

// GET /api/users - List all users
router.get("/users", (req: Request, res: Response) => {
  const users = db.getUsers();
  res.json({
    success: true,
    count: users.length,
    data: users,
  });
});

// GET /api/users/:id - Get a specific user
router.get("/users/:id", (req: Request, res: Response) => {
  const user = db.getUser(req.params.id);

  if (!user) {
    return res.status(404).json({
      success: false,
      error: `User ${req.params.id} not found`,
    });
  }

  res.json({
    success: true,
    data: user,
  });
});

// POST /api/users - Create a new user
router.post("/users", (req: Request, res: Response) => {
  const { name, email, role } = req.body;

  if (!name || !email || !role) {
    return res.status(400).json({
      success: false,
      error: "Missing required fields: name, email, role",
    });
  }

  // Check if email already exists
  if (db.getUserByEmail(email)) {
    return res.status(409).json({
      success: false,
      error: `Email ${email} already exists`,
    });
  }

  const user = db.createUser({ name, email, role });
  res.status(201).json({
    success: true,
    message: "User created successfully",
    data: user,
  });
});

/**
 * Task Routes
 */

// GET /api/tasks - List all tasks with optional filters
router.get("/tasks", (req: Request, res: Response) => {
  const { status, assigned_to } = req.query;

  const tasks = db.getTasks({
    status: status as string | undefined,
    assigned_to: assigned_to as string | undefined,
  });

  res.json({
    success: true,
    count: tasks.length,
    filters: { status, assigned_to },
    data: tasks,
  });
});

// GET /api/tasks/:id - Get a specific task
router.get("/tasks/:id", (req: Request, res: Response) => {
  const task = db.getTask(req.params.id);

  if (!task) {
    return res.status(404).json({
      success: false,
      error: `Task ${req.params.id} not found`,
    });
  }

  res.json({
    success: true,
    data: task,
  });
});

// POST /api/tasks - Create a new task
router.post("/tasks", (req: Request, res: Response) => {
  const { title, description, assigned_to, status } = req.body;

  if (!title || !assigned_to) {
    return res.status(400).json({
      success: false,
      error: "Missing required fields: title, assigned_to",
    });
  }

  // Verify user exists
  if (!db.getUser(assigned_to)) {
    return res.status(404).json({
      success: false,
      error: `User ${assigned_to} not found`,
    });
  }

  const task = db.createTask({
    title,
    description: description || "",
    status: status || "pending",
    assigned_to,
  });

  res.status(201).json({
    success: true,
    message: "Task created successfully",
    data: task,
  });
});

// PUT /api/tasks/:id - Update a task
router.put("/tasks/:id", (req: Request, res: Response) => {
  const { title, description, status, assigned_to } = req.body;

  const task = db.updateTask(req.params.id, {
    ...(title && { title }),
    ...(description && { description }),
    ...(status && { status }),
    ...(assigned_to && { assigned_to }),
  });

  if (!task) {
    return res.status(404).json({
      success: false,
      error: `Task ${req.params.id} not found`,
    });
  }

  res.json({
    success: true,
    message: "Task updated successfully",
    data: task,
  });
});

// DELETE /api/tasks/:id - Delete a task
router.delete("/tasks/:id", (req: Request, res: Response) => {
  // Note: In this simple implementation, we don't have a delete method.
  // For production, you'd implement proper deletion with referential integrity

  res.status(501).json({
    success: false,
    error: "Delete not yet implemented",
  });
});

/**
 * Service Routes
 */

// GET /api/services - List all services
router.get("/services", (req: Request, res: Response) => {
  const services = db.getServices();
  res.json({
    success: true,
    count: services.length,
    data: services,
  });
});

// GET /api/services/:id - Get service status
router.get("/services/:id", (req: Request, res: Response) => {
  const service = db.getService(req.params.id);

  if (!service) {
    return res.status(404).json({
      success: false,
      error: `Service ${req.params.id} not found`,
    });
  }

  res.json({
    success: true,
    data: service,
  });
});

// POST /api/services/:id/restart - Restart a service
router.post("/services/:id/restart", (req: Request, res: Response) => {
  const service = db.updateServiceStatus(req.params.id, "running");

  if (!service) {
    return res.status(404).json({
      success: false,
      error: `Service ${req.params.id} not found`,
    });
  }

  res.json({
    success: true,
    message: `Service ${service.name} restarted successfully`,
    data: service,
  });
});

// POST /api/services/:id/stop - Stop a service
router.post("/services/:id/stop", (req: Request, res: Response) => {
  const service = db.updateServiceStatus(req.params.id, "stopped");

  if (!service) {
    return res.status(404).json({
      success: false,
      error: `Service ${req.params.id} not found`,
    });
  }

  res.json({
    success: true,
    message: `Service ${service.name} stopped successfully`,
    data: service,
  });
});

/**
 * Health Check Route
 */

router.get("/health", (req: Request, res: Response) => {
  res.json({
    success: true,
    status: "ok",
    timestamp: new Date().toISOString(),
  });
});

export default router;
