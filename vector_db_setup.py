# import json
# from langchain_core.documents import Document
# from langchain_community.vectorstores import Chroma
# from langchain_huggingface import HuggingFaceEmbeddings

# def build_vector_database():
#     print("1. Loading Semantic Chunks from JSON...")
#     with open('south_asian_corpus.json', 'r', encoding='utf-8') as f:
#         data = json.load(f)

#     # Convert the JSON array into LangChain Document objects
#     documents = []
#     chunk_ids = []
    
#     for item in data:
#         doc = Document(
#             page_content=item["text"],
#             metadata=item["metadata"]
#         )
#         documents.append(doc)
#         chunk_ids.append(item["id"])
        
#     print(f"Loaded {len(documents)} chunks.")

#     print("2. Initializing BAAI Embedding Model...")
#     # BAAI models require cosine similarity, so normalize_embeddings must be True
#     encode_kwargs = {'normalize_embeddings': True}
    
#     bge_embeddings = HuggingFaceEmbeddings(
#         model_name="BAAI/bge-small-en-v1.5",
#         model_kwargs={'device': 'cpu'}, # Change to 'cuda' if you have an Nvidia GPU
#         encode_kwargs=encode_kwargs
#     )

#     print("3. Creating ChromaDB and embedding chunks (This may take a minute)...")
#     # This embeds your data and saves it to a local folder called "chroma_db"
#     vector_store = Chroma.from_documents(
#         documents=documents,
#         embedding=bge_embeddings,
#         ids=chunk_ids,
#         persist_directory="./chroma_db"
#     )
    
#     print("Vector database created successfully in the './chroma_db' directory!")
#     return vector_store

# def test_retrieval(vector_store):
#     print("\n--- Testing the RAG Retriever ---")
#     # Let's simulate Scenario A: The user asks a direct question
#     query = "How do I make a sweet yogurt dessert?"
#     print(f"User Query: '{query}'\n")
    
#     # Retrieve the top 3 most relevant chunks
#     results = vector_store.similarity_search_with_score(query, k=3)
    
#     for rank, (doc, score) in enumerate(results, 1):
#         # Note: Lower score is better in ChromaDB's default distance metric (L2 distance)
#         print(f"Rank {rank} (Score: {score:.4f})")
#         print(f"Dish: {doc.metadata['dish_name']} | Type: {doc.metadata['content_type']}")
#         print(f"Preview: {doc.page_content[:100]}...\n")

# if __name__ == "__main__":
#     db = build_vector_database()
#     test_retrieval(db)


import json
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

def build_vector_database():
    print("1. Loading Semantic Chunks from JSON...")
    with open('south_asian_corpus.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    documents = []
    
    for item in data:
        # FAISS doesn't need explicit IDs like Chroma, it handles them internally
        doc = Document(
            page_content=item["text"],
            metadata=item["metadata"]
        )
        documents.append(doc)
        
    print(f"Loaded {len(documents)} chunks.")

    print("2. Initializing BAAI Embedding Model...")
    encode_kwargs = {'normalize_embeddings': True}
    
    bge_embeddings = HuggingFaceEmbeddings(
        model_name="BAAI/bge-small-en-v1.5",
        model_kwargs={'device': 'cpu'}, 
        encode_kwargs=encode_kwargs
    )

    print("3. Creating FAISS Vector Store (This may take a minute)...")
    vector_store = FAISS.from_documents(
        documents=documents,
        embedding=bge_embeddings
    )
    
    # Save it locally just like we did with Chroma
    vector_store.save_local("./faiss_index")
    print("Vector database created successfully in the './faiss_index' directory!")
    return vector_store

def test_retrieval(vector_store):
    print("\n--- Testing the RAG Retriever ---")
    query = "How do I make a sweet yogurt dessert?"
    print(f"User Query: '{query}'\n")
    
    # FAISS returns the document and the L2 distance score
    results = vector_store.similarity_search_with_score(query, k=3)
    
    for rank, (doc, score) in enumerate(results, 1):
        print(f"Rank {rank} (Score: {score:.4f})")
        print(f"Dish: {doc.metadata['dish_name']} | Type: {doc.metadata['content_type']}")
        print(f"Preview: {doc.page_content[:100]}...\n")

if __name__ == "__main__":
    db = build_vector_database()
    test_retrieval(db)