/**
 * In-memory database for the Express API
 * In production, use a real database like MongoDB, PostgreSQL, etc.
 */

export interface User {
  id: string;
  name: string;
  email: string;
  role: string;
  created_at: string;
}

export interface Task {
  id: string;
  title: string;
  description: string;
  status: "pending" | "in_progress" | "completed";
  assigned_to: string;
  created_at: string;
  updated_at: string;
}

export interface Service {
  id: string;
  name: string;
  status: "running" | "stopped" | "error";
  last_check: string;
}

class Database {
  private users: Map<string, User> = new Map();
  private tasks: Map<string, Task> = new Map();
  private services: Map<string, Service> = new Map();

  constructor() {
    this.initializeSampleData();
  }

  private initializeSampleData() {
    // Sample users
    this.users.set("user1", {
      id: "user1",
      name: "Alice Johnson",
      email: "alice@example.com",
      role: "admin",
      created_at: new Date().toISOString(),
    });

    this.users.set("user2", {
      id: "user2",
      name: "Bob Smith",
      email: "bob@example.com",
      role: "developer",
      created_at: new Date().toISOString(),
    });

    this.users.set("user3", {
      id: "user3",
      name: "Charlie Brown",
      email: "charlie@example.com",
      role: "developer",
      created_at: new Date().toISOString(),
    });

    // Sample tasks
    this.tasks.set("task1", {
      id: "task1",
      title: "Fix login bug",
      description: "Users cannot login with special characters",
      status: "in_progress",
      assigned_to: "user1",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });

    this.tasks.set("task2", {
      id: "task2",
      title: "Design dashboard",
      description: "Create new dashboard UI mockups",
      status: "pending",
      assigned_to: "user2",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });

    this.tasks.set("task3", {
      id: "task3",
      title: "Write documentation",
      description: "Document API endpoints",
      status: "completed",
      assigned_to: "user3",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });

    // Sample services
    this.services.set("api-server", {
      id: "api-server",
      name: "API Server",
      status: "running",
      last_check: new Date().toISOString(),
    });

    this.services.set("database", {
      id: "database",
      name: "PostgreSQL Database",
      status: "running",
      last_check: new Date().toISOString(),
    });

    this.services.set("cache", {
      id: "cache",
      name: "Redis Cache",
      status: "running",
      last_check: new Date().toISOString(),
    });
  }

  // User methods
  getUsers(): User[] {
    return Array.from(this.users.values());
  }

  getUser(id: string): User | null {
    return this.users.get(id) || null;
  }

  getUserByEmail(email: string): User | null {
    for (const user of this.users.values()) {
      if (user.email === email) return user;
    }
    return null;
  }

  createUser(data: Omit<User, "id" | "created_at">): User {
    const id = `user_${Date.now()}`;
    const user: User = {
      ...data,
      id,
      created_at: new Date().toISOString(),
    };
    this.users.set(id, user);
    return user;
  }

  // Task methods
  getTasks(filters?: { status?: string; assigned_to?: string }): Task[] {
    let tasks = Array.from(this.tasks.values());

    if (filters?.status) {
      tasks = tasks.filter((t) => t.status === filters.status);
    }

    if (filters?.assigned_to) {
      tasks = tasks.filter((t) => t.assigned_to === filters.assigned_to);
    }

    return tasks;
  }

  getTask(id: string): Task | null {
    return this.tasks.get(id) || null;
  }

  createTask(data: Omit<Task, "id" | "created_at" | "updated_at">): Task {
    const id = `task_${Date.now()}`;
    const task: Task = {
      ...data,
      id,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    this.tasks.set(id, task);
    return task;
  }

  updateTask(id: string, data: Partial<Task>): Task | null {
    const task = this.tasks.get(id);
    if (!task) return null;

    const updated = {
      ...task,
      ...data,
      id: task.id, // Don't allow id change
      created_at: task.created_at, // Don't allow creation time change
      updated_at: new Date().toISOString(),
    };

    this.tasks.set(id, updated);
    return updated;
  }

  // Service methods
  getServices(): Service[] {
    return Array.from(this.services.values());
  }

  getService(id: string): Service | null {
    return this.services.get(id) || null;
  }

  updateServiceStatus(
    id: string,
    status: "running" | "stopped" | "error"
  ): Service | null {
    const service = this.services.get(id);
    if (!service) return null;

    const updated = {
      ...service,
      status,
      last_check: new Date().toISOString(),
    };

    this.services.set(id, updated);
    return updated;
  }
}

// Export singleton instance
export const db = new Database();
