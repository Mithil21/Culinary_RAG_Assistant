from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

print("Loading FAISS...")
bge_embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-small-en-v1.5", model_kwargs={"device": "cpu"}, encode_kwargs={"normalize_embeddings": True})
vector_store = FAISS.load_local("./faiss_index", bge_embeddings, allow_dangerous_deserialization=True)

# Pull the top chunk for 'chicken'
doc = vector_store.similarity_search("chicken", k=1)[0]

print("\n--- RAW FAISS METADATA ---")
print(doc.metadata)
print("--------------------------\n")