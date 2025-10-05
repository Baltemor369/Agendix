import sqlite3
from dataclasses import dataclass, fields, asdict
from typing import Optional, List, Type, TypeVar, Any

T = TypeVar("T")  # Type générique pour les dataclasses


class BaseModel:
    table: str   # Nom de la table (doit être défini dans chaque classe)
    pk: str = "id"  # Nom de la clé primaire (par défaut: id)

    @classmethod
    def from_row(cls: Type[T], row: sqlite3.Row) -> T:
        """Crée un objet dataclass depuis un row SQLite"""
        kwargs = {f.name: row[f.name] for f in fields(cls) if f.name in row.keys()}
        return cls(**kwargs)

    @classmethod
    def get_by_id(cls: Type[T], conn: sqlite3.Connection, id_: int) -> Optional[T]:
        c = conn.cursor()
        c.execute(f"SELECT * FROM {cls.table} WHERE {cls.pk} = ?", (id_,))
        row = c.fetchone()
        return cls.from_row(row) if row else None

    @classmethod
    def all(cls: Type[T], conn: sqlite3.Connection) -> List[T]:
        c = conn.cursor()
        c.execute(f"SELECT * FROM {cls.table}")
        rows = c.fetchall()
        return [cls.from_row(row) for row in rows]

    def save(self, conn: sqlite3.Connection) -> None:
        """Insert ou Update selon que l'objet a déjà un id ou pas"""
        c = conn.cursor()
        data = asdict(self)
        cols = [f.name for f in fields(self) if f.name != self.pk]
        vals = [data[col] for col in cols]

        if getattr(self, self.pk) is None:  # INSERT
            placeholders = ", ".join("?" for _ in cols)
            c.execute(
                f"INSERT INTO {self.table} ({', '.join(cols)}) VALUES ({placeholders})",
                vals
            )
            setattr(self, self.pk, c.lastrowid)
        else:  # UPDATE
            set_clause = ", ".join(f"{col} = ?" for col in cols)
            c.execute(
                f"UPDATE {self.table} SET {set_clause} WHERE {self.pk} = ?",
                vals + [getattr(self, self.pk)]
            )

        conn.commit()

    def delete(self, conn: sqlite3.Connection) -> None:
        c = conn.cursor()
        c.execute(
            f"DELETE FROM {self.table} WHERE {self.pk} = ?",
            (getattr(self, self.pk),)
        )
        conn.commit()
