from threading import RLock


class OptionCache:
    def __init__(self):
        self.lock = RLock()
        self.options = {}

    def reload(self, repo):
        data = repo.options()
        with self.lock:
            self.options = data

    def get(self):
        with self.lock:
            return dict(self.options)

    def save(self, repo, options):
        # Do not persist credential material that Spring accidentally bound as options.
        repo.save_options({key: value for key, value in options.items() if key != "_csrf"})
        repo.db.commit()
        self.reload(repo)
