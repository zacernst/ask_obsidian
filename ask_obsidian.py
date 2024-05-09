import markdown
import pathlib
import chromadb
import hashlib
from rich.progress import Progress, SpinnerColumn, MofNCompleteColumn
import uuid
from typing import Optional

from langchain_openai import ChatOpenAI


class QASession:
    def __init__(self, vault_path: str, collection_name: Optional[str] = None):
        self.collection_name = collection_name or uuid.uuid4().hex
        self.vault_path = vault_path
        self.collection = self.collection_from_vault(self.vault_path)
        self.llm = ChatOpenAI()

    def markdown_paths(self, progress_message: Optional[str] = "Walking vault"):
        path = pathlib.Path(self.vault_path)
        for current_path, directories, filenames in path.walk():
            with Progress(
                SpinnerColumn(),
                *Progress.get_default_columns(),
                MofNCompleteColumn(),
                transient=True,
                expand=False,
            ) as pbar:
                task = pbar.add_task(progress_message, total=len(filenames))
                for filename in filenames:
                    if not filename.endswith("md"):
                        continue
                    markdown_path = current_path.joinpath(filename)
                    yield markdown_path
                    pbar.update(task, advance=1)

    def markdown_files(self, progress_message: Optional[str] = "Yielding documents"):
        md = markdown.Markdown()
        for markdown_path in self.markdown_paths(progress_message=progress_message):
            with open(markdown_path, "r") as f:
                text = f.read()
                yield markdown_path, md.convert(text)

    def collection_from_vault(
        self, progress_message: Optional[str] = "Building collection"
    ):
        chroma_client = chromadb.Client()
        collection = chroma_client.create_collection(name=self.collection_name)
        for markdown_path, markdown_text in self.markdown_files(
            progress_message=progress_message
        ):
            hexdigest = hashlib.md5(bytes(markdown_text, encoding="utf")).hexdigest()
            collection.add(
                documents=[markdown_text],
                metadatas=[{"source": str(markdown_path), "hash": hexdigest}],
                ids=[hexdigest],
            )
        return collection

    def related_documents(
        self,
        query: str,
        num_results: int = 2,
    ):
        results = self.collection.query(query_texts=[query], n_results=num_results)
        documents = results["documents"][0]
        for document in documents:
            yield document

    def ask(self, question: str):
        documents = "\n".join(list(self.related_documents(question)))
        full_question = (
            f"""You are a helpful assistant. Answer the question "{question}" using information """
            f"""contained in the following documents: {documents}"""
        )
        answer = self.llm.invoke(full_question)
        return answer.content


if __name__ == "__main__":
    VAULT_PATH = "/Users/zac/git/obsidian_llm/vault"
    session = QASession(VAULT_PATH)
    answer = session.ask(
        "Give me a couple of very brief hints for how I might use Obsidian for scheduling."
    )
    print(answer)

    # Output:
    # 1. Enable the Daily Notes Core plugin in Obsidian to create or open daily notes.
    # 2. Install and enable the Day Planner Community plugin to set up time blocking schedules within your daily notes.

