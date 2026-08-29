#Full text download via PubMed Central NCBI E-utilities API
library(readxl)
library(rentrez)
library(httr) 
library(dplyr)
library(purrr)
library(writexl)
api_key<-"....."   #API key

request_delay<-ifelse(is.null(api_key) || api_key=="",0.34,0.2)

pmc_ncbi_eutilities_api<-".../Pubcentral"
output_dir<-".../Pubcentral/Full text"   #Full text output file
dir.create(output_dir,showWarnings=FALSE,recursive=TRUE)
#Error record files
no_pmcid_file<-paste0(pmc_ncbi_eutilities_api,"/no_pmcid_dois.txt")
non_oa_file<-paste0(pmc_ncbi_eutilities_api,"/non_oa_dois.txt")

no_pmcid_dois<-character()
non_oa_dois<-character()


#Read input DOIs or PMCIDs
input_file<-".../doi_list.xlsx"
df_articles<-read_excel(input_file)
cat("Successfully read ",nrow(df_articles)," literature\n")

colnames(df_articles)<-toupper(colnames(df_articles))
safe_entrez_search<-safely(entrez_search)

search_results<-map(df_articles$DOI,function(doi){
  query<-paste0(doi,"[DOI]")
  result<-safe_entrez_search(
    db="pmc", 
    term=query, 
    api_key=api_key
  )
  Sys.sleep(request_delay)
  return(result)
})

pmc_ids<-map_chr(search_results,~{
  if(!is.null(.x$result) && .x$result$count>0){
    .x$result$ids[1]   
  } else {
    NA_character_
  }
})
results_df<-df_articles %>%
  mutate(
    PMCID=pmc_ids,
    Download_Status=ifelse(is.na(PMCID),"No_PMCID","PMCID_Found")
  )

no_pmcid_dois<-results_df$DOI[is.na(results_df$PMCID)]

found_count<-sum(!is.na(results_df$PMCID))
cat("Sucessfully find",found_count,"/",nrow(results_df)," PMCID for lituratures\n")
cat("Literautre without PMCIDs: ",length(no_pmcid_dois),"\n")


#Full text download function
#XML format
download_xml<-function(pmcid,doi,title,output_dir,api_key){
  tryCatch({
    fulltext_xml<-entrez_fetch(
      db="pmc", 
      id=pmcid, 
      rettype="xml",
      api_key=api_key
    )
    
    if(grepl("<!DOCTYPE",fulltext_xml,ignore.case=TRUE) && grepl("<article",fulltext_xml,ignore.case=TRUE)){
      safe_doi<-gsub("[^a-zA-Z0-9.-]","_",doi)
      safe_doi<-gsub("/","_",safe_doi)  
      filename<-file.path(output_dir,paste0(safe_doi,".xml"))
      writeLines(fulltext_xml,con=filename)
      return("XML_Success")
    } else {
      
      message(paste("Non-OA literature, unable to obtain the full text: ",pmcid,"-",doi))
      return("Non_OA_Access_Denied")
    }
  },error=function(e){
    
    error_msg<-tolower(e$message)
    if(grepl("permission|access|rights|restricted|denied",error_msg)){
      message(paste("Non-OA literature, access denied",pmcid,"-",doi,"-",e$message))
      return("Non_OA_Access_Denied")
    } else {
      message(paste("XML download failed: ",pmcid,"-",doi,"-",e$message))
      return("XML_Failed")
    }
  })
}

cat("Start to download full text...\n")
valid_articles<-results_df %>% filter(!is.na(PMCID))

download_results<-pmap_chr(
  list(
    valid_articles$PMCID, 
    valid_articles$DOI,
    valid_articles$TITLE
  ),
  ~{
    result<-download_xml(..1,..2,..3,output_dir,api_key)
    Sys.sleep(request_delay)
    return(result)
  }
)

results_df<-results_df %>%
  left_join(
    valid_articles %>%
      mutate(Download_Status=download_results) %>%
      select(DOI,Download_Status),
    by="DOI"
  ) %>%
  mutate(
    Download_Status=coalesce(Download_Status.y,Download_Status.x)
  ) %>%
  select(-Download_Status.x,-Download_Status.y)

non_oa_dois<-results_df$DOI[results_df$Download_Status=="Non_OA_Access_Denied"]


if(length(no_pmcid_dois)>0){
  writeLines(no_pmcid_dois,no_pmcid_file)
  cat("DOI without PMCID has been saved to:",no_pmcid_file,"\n")
} else {
  cat("All literature has found PMCID\n")
}
if(length(non_oa_dois)>0){
  writeLines(non_oa_dois,non_oa_file)
  cat("DOI of non-OA literature has been saved to:",non_oa_file,"\n")
} else {
  cat("All literature with PMCID is open access\n")
}

report_file<-paste0(output_dir,"download_report_",format(Sys.Date(),"%Y%m%d"),".xlsx")
write_xlsx(results_df,report_file)

success_count<-sum(results_df$Download_Status %in% c("XML_Success","PDF_Success"))
failed_count<-sum(results_df$Download_Status %in% c("XML_Failed","PDF_Failed"))
non_oa_count<-sum(results_df$Download_Status=="Non_OA_Access_Denied")
no_pmcid_count<-sum(results_df$Download_Status=="No_PMCID")
cat("\n=== Download complete ===\n")
cat("Total literautre:",nrow(results_df),"\n")
cat("Successfully download:",success_count,"\n")
cat("Failed:",failed_count,"\n")
cat("Non-OA:",non_oa_count,"\n")
cat("Without PMCID:",no_pmcid_count,"\n")