module.exports = {
  apps: [
    {
      name: "movie-night-api",
      cwd: "/home/skillseek/app/backend",
      // ВАЖНО: запускаем непосредственно python как "script"
      script: "/home/skillseek/app/backend/.venv/bin/python",
      // Аргументы: модуль uvicorn и параметры
      args: "-m uvicorn server:app --host 0.0.0.0 --port 8000 --workers 2",
      // Критично: говорим PM2 НЕ использовать node как интерпретатор
      interpreter: "none",
      env: {
        PYTHONPATH: "/home/skillseek/app/backend"
      },
      autorestart: true,
      watch: false,
      time: true,
      max_restarts: 10
    },
    {
      name: "imdb-loader-daily",
      cwd: "/home/skillseek/app/backend",
      script: "/home/skillseek/app/backend/.venv/bin/python",
      args: "load_imdb.py",
      interpreter: "none",
      cron_restart: "0 5 * * *",
      autorestart: false,
      watch: false,
      time: true
    }
  ]
}
