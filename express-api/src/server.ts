import express from "express";
import cors from "cors";
import routes from "./routes";

const app = express();
const PORT = process.env.PORT || 3001;

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Routes
app.use("/api", routes);

// Root endpoint
app.get("/", (req, res) => {
  res.json({
    message: "Express API Server for Agentic AI",
    version: "1.0.0",
    endpoints: {
      users: {
        list: "GET /api/users",
        get: "GET /api/users/:id",
        create: "POST /api/users",
      },
      tasks: {
        list: "GET /api/tasks",
        get: "GET /api/tasks/:id",
        create: "POST /api/tasks",
        update: "PUT /api/tasks/:id",
      },
      services: {
        list: "GET /api/services",
        get: "GET /api/services/:id",
        restart: "POST /api/services/:id/restart",
        stop: "POST /api/services/:id/stop",
      },
      health: "GET /api/health",
    },
  });
});

// Error handler
app.use(
  (
    err: any,
    req: express.Request,
    res: express.Response,
    next: express.NextFunction
  ) => {
    console.error("Error:", err);
    res.status(500).json({
      success: false,
      error: "Internal server error",
      message: err.message,
    });
  }
);

// 404 handler
app.use((req: express.Request, res: express.Response) => {
  res.status(404).json({
    success: false,
    error: "Not found",
    path: req.path,
  });
});

app.listen(PORT, () => {
  console.log(`\n✅ Express API Server running on http://localhost:${PORT}`);
  console.log(`\n📚 Available endpoints:`);
  console.log(`   Users:    GET /api/users`);
  console.log(`   Tasks:    GET /api/tasks`);
  console.log(`   Services: GET /api/services`);
  console.log(`   Health:   GET /api/health`);
  console.log(
    `\n🔗 Visit http://localhost:${PORT} for full API documentation\n`
  );
});
