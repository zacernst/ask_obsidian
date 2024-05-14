import click
import hashlib
import pathlib
import os
from typing import Optional
import uuid

from bs4 import BeautifulSoup
import chromadb
from langchain_openai import ChatOpenAI
import markdown
import rich
from rich.progress import Progress, SpinnerColumn, MofNCompleteColumn

# To suppress some warnings that are annoying
os.environ["TOKENIZERS_PARALLELISM"] = "false"


class QASession:
    """
    A class to represent a Q&A session with an Obsidian vault.
    This is testing my git setup...
    """

    def __init__(self, vault_path: str, collection_name: Optional[str] = None):
        self.collection_name = collection_name or uuid.uuid4().hex
        self.vault_path = vault_path
        self.collection = self.collection_from_vault(self.vault_path)
        self.llm = ChatOpenAI()

    def markdown_paths(self, progress_message: Optional[str] = "Walking vault"):
        """
        Walk the vault and yield the paths to any Markdown files.
        """
        path = pathlib.Path(self.vault_path)
        for current_path, _, filenames in path.walk():
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
        """
        Yield the contents of the Markdown files in the vault.
        """

        def _convert(text: str) -> str:
            """
            Convert from Markdown to HTML, and then to text.
            """
            md = markdown.Markdown()
            result = BeautifulSoup(md.convert(text), features="html.parser").get_text()
            return result

        for markdown_path in self.markdown_paths(progress_message=progress_message):
            with open(markdown_path, "r") as f:
                text = f.read()
                yield markdown_path, _convert(text)

    def collection_from_vault(
        self, progress_message: Optional[str] = "Building collection"
    ):
        """
        Create a ChromaDB collection from the Markdown files in the vault.
        """
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
        """
        Yield `num_results` related documents for a query.
        """
        results = self.collection.query(query_texts=[query], n_results=num_results)
        documents = results["documents"][0]
        for document in documents:
            yield document

    def ask(self, question: str):
        """
        Ask a question and get an answer.
        """
        documents = "\n".join(list(self.related_documents(question)))
        full_question = (
            f"""You are a helpful assistant. Answer the question "{question}" using information """
            f"""contained in the following documents: {documents}."""
        )
        answer = self.llm.invoke(full_question)
        return answer.content


@click.command()
@click.option(
    "--vault-path",
    default="/Users/zac/git/obsidian_llm/vault",
    help="Path to the Obsidian vault",
)
@click.option(
    "--question", prompt="Question", help="Question to ask the Obsidian vault"
)
def main(vault_path: str, question: str) -> None:
    """
    Ask a question to an Obsidian vault. Pretty-print the answer.
    """
    session = QASession(vault_path)
    answer = session.ask(question)
    rich.print(answer)


if __name__ == "__main__":
    main()
