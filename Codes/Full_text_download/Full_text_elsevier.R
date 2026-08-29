#Full text download via Elsevier Article (Full Text) Retrieval API
library(httr)
library(readxl)
library(dplyr)
library(fs)

API_KEY<-"....."   #Elsevier API Key
DOI_FILE<-".../doi_list.xlsx"    #File path storing all DOIs
OUTPUT_DIR<-".../Full text"   #Output file
NOT_ELSEVIER_FILE<-".../not_elsevier_dois.txt"   #File for recording unauthorized DOIs
NO_FULLTEXT_FILE<-".../no_fulltext_dois.txt"   #File for recording non-ScienceDirect literature

dois<-read_excel(DOI_FILE) %>% pull(doi) %>% na.omit() %>% unique()
not_elsevier_dois<-c()
no_fulltext_dois<-c()

#Try to download XML format files through DOI
for(doi in dois){
  xml_filename<-paste0(gsub("/","_",doi),".xml")
  xml_path<-path(OUTPUT_DIR,xml_filename)
  
  if(file_exists(xml_path)){
    message(sprintf("Skip: %s already existed",doi))
    next
  }
  
  url<-sprintf(
    "https://api.elsevier.com/content/article/doi/%s",doi)
  
  response<-GET(
    url,
    add_headers("X-ELS-APIKey"=API_KEY,"Accept"="application/xml")
  )
  
  status<-status_code(response)
  if(status==200){
    content_type<-headers(response)$`content-type`
    if(grepl("application/xml|text/xml",content_type)){
  
      writeBin(content(response,"raw"),xml_path)
      message(sprintf("Download success: %s",doi))
    } else {
      
      not_elsevier_dois<-c(not_elsevier_dois,doi)
      message(sprintf("Non-Elsevier literature: %s (response type:%s)",doi,content_type))
    }
  } else if (status==404){
    
    not_elsevier_dois<-c(not_elsevier_dois,doi)
    message(sprintf("Non-Elsevier literature: %s (DOI not exist)",doi))
  } else if (status == 403 || status == 401){
   
    no_fulltext_dois<-c(no_fulltext_dois, doi)
    message(sprintf("No full-text authorization: %s (Status code: %d)",doi,status))
  } else {
    
    not_elsevier_dois<-c(not_elsevier_dois,doi)
    message(sprintf("Failed: %s (Status code: %d)",doi,status))
  }
  
  Sys.sleep(1)
}

#Saving results
if(length(not_elsevier_dois)>0){
  writeLines(not_elsevier_dois,NOT_ELSEVIER_FILE)
  message(sprintf("Non Elsevier literature DOI has been saved to: %s",NOT_ELSEVIER_FILE))
}
if(length(no_fulltext_dois)>0){
  writeLines(no_fulltext_dois,NO_FULLTEXT_FILE)
  message(sprintf("DOI without full text authorization has been saved to: %s",NO_FULLTEXT_FILE))
}

message(sprintf("Successfully download: %d",length(dois)-length(not_elsevier_dois)-length(no_fulltext_dois)))
message(sprintf("Non-Elsevier: %d",length(not_elsevier_dois)))
message(sprintf("No full text authorization: %d",length(no_fulltext_dois)))